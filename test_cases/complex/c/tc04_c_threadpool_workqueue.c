#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

#define MAX_QUEUE_ITEMS 32
#define TASK_NAME_LEN 32

typedef enum {
    TASK_PRIORITY_LOW = 0,
    TASK_PRIORITY_MEDIUM = 1,
    TASK_PRIORITY_HIGH = 2,
    TASK_PRIORITY_CRITICAL = 3
} TaskPriority;

typedef struct {
    uint32_t taskId;
    char taskName[TASK_NAME_LEN];
    TaskPriority priority;
    int payloadEstimateMs;
    bool isCompleted;
} WorkTask;

typedef struct {
    WorkTask queue[MAX_QUEUE_ITEMS];
    size_t head;
    size_t tail;
    size_t count;
    uint32_t totalDispatched;
} TaskQueue;

void taskQueueInit(TaskQueue* tq) {
    if (!tq) return;
    tq->head = 0;
    tq->tail = 0;
    tq->count = 0;
    tq->totalDispatched = 0;
    memset(tq->queue, 0, sizeof(tq->queue));
}

bool taskQueueEnqueue(TaskQueue* tq, const WorkTask* task) {
    if (!tq || !task || tq->count >= MAX_QUEUE_ITEMS) return false;
    tq->queue[tq->tail] = *task;
    tq->tail = (tq->tail + 1) % MAX_QUEUE_ITEMS;
    tq->count++;
    tq->totalDispatched++;
    return true;
}

bool taskQueueDequeue(TaskQueue* tq, WorkTask* outTask) {
    if (!tq || !outTask || tq->count == 0) return false;
    *outTask = tq->queue[tq->head];
    tq->head = (tq->head + 1) % MAX_QUEUE_ITEMS;
    tq->count--;
    return true;
}


typedef struct {
    uint32_t monitoredTasks;
    double maxLatencyRecorded;
} TaskExecutionProfiler;

void recordProfileSample(TaskExecutionProfiler* p, double lat) {
    if (!p) return;
    p->monitoredTasks++;
    if (lat > p->maxLatencyRecorded) p->maxLatencyRecorded = lat;
}

bool taskQueuePeek(const TaskQueue* tq, WorkTask* outTask) {
    if (!tq || !outTask || tq->count == 0) return false;
    *outTask = tq->queue[tq->head];
    return true;
}

const char* priorityToString(TaskPriority p) {
    switch (p) {
        case TASK_PRIORITY_LOW: return "LOW";
        case TASK_PRIORITY_MEDIUM: return "MEDIUM";
        case TASK_PRIORITY_HIGH: return "HIGH";
        case TASK_PRIORITY_CRITICAL: return "CRITICAL";
        default: return "UNKNOWN";
    }
}

void executeWorkTask(WorkTask* t) {
    if (!t) return;
    printf("  [WORKER-EXEC] Running Task #%u ('%s') | Priority: %s | Est: %d ms\n",
           t->taskId, t->taskName, priorityToString(t->priority), t->payloadEstimateMs);
    t->isCompleted = true;
}

void printQueueReport(const TaskQueue* tq) {
    if (!tq) return;
    printf("\n=== Task Work Queue Status ===\n");
    printf("Queue Size : %zu / %d\n", tq->count, MAX_QUEUE_ITEMS);
    printf("Dispatched : %u tasks\n", tq->totalDispatched);
    printf("Head Index : %zu | Tail Index: %zu\n", tq->head, tq->tail);
    printf("==============================\n");
}

typedef struct {
    double averageExecutionMs;
    uint32_t tasksExecuted;
} WorkerTelemetryStats;

void recordTaskTelemetry(WorkerTelemetryStats* stats, int durMs) {
    if (!stats) return;
    stats->tasksExecuted++;
    stats->averageExecutionMs = 0.9 * stats->averageExecutionMs + 0.1 * durMs;
}

void printTelemetryStats(const WorkerTelemetryStats* stats) {
    if (!stats) return;
    printf("Worker Telemetry: Total Executed=%u | Rolling Mean=%0.2f ms\n",
           stats->tasksExecuted, stats->averageExecutionMs);
}

void runTaskSchedulerBanner(void) {
    printf("============================================================\n");
    printf("    C11 EMBEDDED TASK SCHEDULER & DISPATCH RUNQUEUE         \n");
    printf("    Priority-Aware Execution & Lifecycle Profiling          \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [TASK-SLOT-%02d] Initializing dispatch queue slot %d.\n", k, k);
    }
}

int main(void) {
    runTaskSchedulerBanner();
    TaskQueue tq;
    taskQueueInit(&tq);

    WorkerTelemetryStats stats = {15.0, 0};

    for (uint32_t i = 1; i <= 6; ++i) {
        WorkTask t;
        t.taskId = 200 + i;
        snprintf(t.taskName, sizeof(t.taskName), "AST_CODEGEN_TASK_%u", i);
        t.priority = (TaskPriority)(i % 4);
        t.payloadEstimateMs = (int)(i * 12);
        t.isCompleted = false;

        taskQueueEnqueue(&tq, &t);
    }

    printQueueReport(&tq);

    WorkTask activeTask;
    while (taskQueueDequeue(&tq, &activeTask)) {
        executeWorkTask(&activeTask);
        recordTaskTelemetry(&stats, activeTask.payloadEstimateMs);
    }

    printTelemetryStats(&stats);
    return 0;
}
