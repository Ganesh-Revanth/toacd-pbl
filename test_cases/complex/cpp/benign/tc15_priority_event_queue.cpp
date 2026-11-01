#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <iomanip>
#include <chrono>

struct ScheduledTaskEvent {
    int taskId;
    int priority; // lower value = higher urgency
    long long scheduledTimestampMs;
    std::string taskName;

    ScheduledTaskEvent() : taskId(0), priority(100), scheduledTimestampMs(0) {}
    ScheduledTaskEvent(int id, int prio, long long ts, std::string name)
        : taskId(id), priority(prio), scheduledTimestampMs(ts), taskName(std::move(name)) {}

    bool isHigherPriorityThan(const ScheduledTaskEvent& other) const {
        if (priority != other.priority) return priority < other.priority;
        return scheduledTimestampMs < other.scheduledTimestampMs;
    }
};

class BinaryMinHeapQueue {
private:
    std::vector<ScheduledTaskEvent> heap;

    size_t parent(size_t i) const { return (i - 1) / 2; }
    size_t leftChild(size_t i) const { return 2 * i + 1; }
    size_t rightChild(size_t i) const { return 2 * i + 2; }

    void siftUp(size_t i) {
        while (i > 0 && heap[i].isHigherPriorityThan(heap[parent(i)])) {
            std::swap(heap[i], heap[parent(i)]);
            i = parent(i);
        }
    }

    void siftDown(size_t i) {
        size_t minIndex = i;
        size_t l = leftChild(i);
        size_t r = rightChild(i);

        if (l < heap.size() && heap[l].isHigherPriorityThan(heap[minIndex])) {
            minIndex = l;
        }
        if (r < heap.size() && heap[r].isHigherPriorityThan(heap[minIndex])) {
            minIndex = r;
        }

        if (i != minIndex) {
            std::swap(heap[i], heap[minIndex]);
            siftDown(minIndex);
        }
    }

public:
    void push(const ScheduledTaskEvent& event) {
        heap.push_back(event);
        siftUp(heap.size() - 1);
    }

    ScheduledTaskEvent pop() {
        if (heap.empty()) throw std::underflow_error("Priority queue is empty");
        ScheduledTaskEvent top = heap.front();
        heap.front() = heap.back();
        heap.pop_back();
        if (!heap.empty()) siftDown(0);
        return top;
    }

    const ScheduledTaskEvent& peek() const {
        if (heap.empty()) throw std::underflow_error("Priority queue is empty");
        return heap.front();
    }

    bool cancelTask(int taskId) {
        for (size_t i = 0; i < heap.size(); ++i) {
            if (heap[i].taskId == taskId) {
                heap[i] = heap.back();
                heap.pop_back();
                if (i < heap.size()) {
                    siftDown(i);
                    siftUp(i);
                }
                return true;
            }
        }
        return false;
    }

    bool updatePriority(int taskId, int newPriority) {
        for (size_t i = 0; i < heap.size(); ++i) {
            if (heap[i].taskId == taskId) {
                int oldPrio = heap[i].priority;
                heap[i].priority = newPriority;
                if (newPriority < oldPrio) {
                    siftUp(i);
                } else {
                    siftDown(i);
                }
                return true;
            }
        }
        return false;
    }

    std::vector<ScheduledTaskEvent> drainAll() {
        std::vector<ScheduledTaskEvent> drained;
        while (!heap.empty()) {
            drained.push_back(pop());
        }
        return drained;
    }

    bool empty() const { return heap.empty(); }
    size_t size() const { return heap.size(); }

    void dumpHeapOrder() const {
        std::cout << "\n================ MIN-HEAP PRIORITY QUEUE ================\n";
        std::cout << "Total Queued Tasks: " << heap.size() << "\n";
        for (size_t i = 0; i < heap.size(); ++i) {
            std::cout << "  [" << std::setw(2) << i << "] Priority: " << std::setw(3) << heap[i].priority
                      << " | ID: " << std::setw(4) << heap[i].taskId
                      << " | Name: " << heap[i].taskName << "\n";
        }
        std::cout << "=========================================================\n";
    }
};

int main() {
    BinaryMinHeapQueue taskQueue;

    taskQueue.push(ScheduledTaskEvent(101, 5, 1000, "Background Log Flush"));
    taskQueue.push(ScheduledTaskEvent(102, 1, 1050, "Security Patch Validation"));
    taskQueue.push(ScheduledTaskEvent(103, 3, 1100, "AST Garbage Collection"));
    taskQueue.push(ScheduledTaskEvent(104, 1, 1020, "Compiler Error Auto-Heal"));
    taskQueue.push(ScheduledTaskEvent(105, 10, 1200, "Daily Telemetry Export"));
    taskQueue.push(ScheduledTaskEvent(106, 2, 1010, "High-Priority Sandbox Audit"));

    taskQueue.dumpHeapOrder();

    std::cout << "\nUpdating Task 105 Priority from 10 to 0 (Critical Emergency):\n";
    taskQueue.updatePriority(105, 0);
    taskQueue.dumpHeapOrder();

    std::cout << "\nCancelling Task 103 (AST Garbage Collection): "
              << (taskQueue.cancelTask(103) ? "CANCELLED" : "NOT_FOUND") << "\n";
    taskQueue.dumpHeapOrder();

    std::cout << "\nProcessing tasks by strict priority dispatch:\n";
    while (!taskQueue.empty()) {
        auto top = taskQueue.pop();
        std::cout << "  -> Dispatched Task [" << top.taskId << "] '" << top.taskName
                  << "' (Priority " << top.priority << ")\n";
    }

    return 0;
}
