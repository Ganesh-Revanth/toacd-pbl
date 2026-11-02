#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

// Complex broken C program for self-healing compiler benchmark
// Circular FIFO ring buffer for streaming telemetry events
// Contains 3-5 distinct C compilation faults (150-500 LOC)

#define RING_BUFFER_CAPACITY 32

typedef struct {
    int eventId;
    double timestamp;
    char payload[32];
} StreamEvent;

typedef struct {
    StreamEvent buffer[RING_BUFFER_CAPACITY];
    size_t head;
    size_t tail;
    size_t count;
    bool isFull;
} CircularRingBuffer;

typedef struct {
    char streamSource[32];
    double averageLatencyMs;
    size_t overflowCount;
} StreamTelemetry;

void printStreamTelemetry(const StreamTelemetry* telem) {
    if (!telem) return;
    printf("[STREAM-TELEMETRY] Source: %s | Latency: %.2f ms | Overflows: %zu\n",
           telem->streamSource, telem->averageLatencyMs, telem->overflowCount);
}

// ERROR 1: Missing return type on function
initRingBuffer(CircularRingBuffer* rb) {
    if (!rb) return;
    rb->head = 0;
    rb->tail = 0;
    rb->count = 0;
    rb->isFull = false;
    memset(rb->buffer, 0, sizeof(rb->buffer));
}

bool pushRingEvent(CircularRingBuffer* rb, int eventId, double ts, const char* data) {
    if (!rb) return false;

    // ERROR 2: Undeclared variable 'ringMaxCapacityLimit'
    if (rb->count >= ringMaxCapacityLimit) {
        return false;
    }

    rb->buffer[rb->head].eventId = eventId;
    rb->buffer[rb->head].timestamp = ts;

    // ERROR 3: Incompatible pointer assignment without cast
    rb->buffer[rb->head].payload = "cannot_assign_string_literal_to_array";

    rb->head = (rb->head + 1) % RING_BUFFER_CAPACITY;
    if (rb->isFull) {
        rb->tail = (rb->tail + 1) % RING_BUFFER_CAPACITY;
    } else {
        rb->count++;
        if (rb->count == RING_BUFFER_CAPACITY) {
            rb->isFull = true;
        }
    }
    return true;
}

bool popRingEvent(CircularRingBuffer* rb, StreamEvent* outEvent) {
    if (!rb || !outEvent || rb->count == 0) {
        return false;
    }
    *outEvent = rb->buffer[rb->tail];
    rb->tail = (rb->tail + 1) % RING_BUFFER_CAPACITY;
    rb->isFull = false;
    rb->count--;
    return true;
}

void printBufferStatus(const CircularRingBuffer* rb) {
    if (!rb) return;
    printf("\n=== Circular Ring Buffer Status ===\n");
    printf("Item Count: %zu / %d\n", rb->count, RING_BUFFER_CAPACITY);
    printf("Head Index: %zu | Tail Index: %zu\n", rb->head, rb->tail);
    printf("Is Full:    %s\n", rb->isFull ? "YES" : "NO");
}

void runRingBufferHeader(void) {
    printf("============================================================\n");
    printf("   C11 CIRCULAR FIFO RING BUFFER BENCHMARK                 \n");
    printf("   Multi-Fault Broken Benchmark Fixture (3-5 Faults)        \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [RING-SLOT-PREFLIGHT-%02d] Checking ring buffer slot %d.\n", k, k);
    }
}

int main(void) {
    runRingBufferHeader();

    StreamTelemetry streamInfo = {"SENSOR_BUS_01", 1.45, 0};
    printStreamTelemetry(&streamInfo);

    CircularRingBuffer rb;
    initRingBuffer(&rb);

    pushRingEvent(&rb, 101, 1000.1, "TEMP_READING_OK");
    pushRingEvent(&rb, 102, 1000.2, "VOLTAGE_READING_OK");

    printBufferStatus(&rb);

    StreamEvent evt;
    if (popRingEvent(&rb, &evt)) {
        printf("Popped Event #%d at %.2f\n", evt.eventId, evt.timestamp);
    }

    printBufferStatus(&rb);

    // ERROR 4: Calling non-existent function
    compactRingBufferMemoryFootprint(&rb);

    return 0;
}

