#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

#define ARENA_CAPACITY_BYTES (64 * 1024)

typedef struct {
    uint8_t buffer[ARENA_CAPACITY_BYTES];
    size_t offset;
    size_t allocationCount;
    size_t totalRequestedBytes;
} MemoryArena;

void arenaInit(MemoryArena* arena) {
    if (!arena) return;
    arena->offset = 0;
    arena->allocationCount = 0;
    arena->totalRequestedBytes = 0;
    memset(arena->buffer, 0, sizeof(arena->buffer));
}

void* arenaAlloc(MemoryArena* arena, size_t bytes, size_t alignment) {
    if (!arena || bytes == 0) return NULL;
    if (alignment == 0) alignment = sizeof(void*);

    size_t currentAddr = (size_t)(arena->buffer + arena->offset);
    size_t padding = (alignment - (currentAddr % alignment)) % alignment;

    if (arena->offset + padding + bytes > ARENA_CAPACITY_BYTES) {
        return NULL; // Out of memory in linear arena
    }

    arena->offset += padding;
    void* ptr = &arena->buffer[arena->offset];
    arena->offset += bytes;

    arena->allocationCount++;
    arena->totalRequestedBytes += bytes;
    return ptr;
}

void* arenaAllocZero(MemoryArena* arena, size_t bytes, size_t alignment) {
    void* p = arenaAlloc(arena, bytes, alignment);
    if (p) memset(p, 0, bytes);
    return p;
}

void arenaReset(MemoryArena* arena) {
    if (!arena) return;
    arena->offset = 0;
    arena->allocationCount = 0;
}


typedef struct {
    size_t memoryThresholdBytes;
    bool enableLeakWarnings;
} ArenaConfigPolicy;

void configureArenaPolicy(ArenaConfigPolicy* pol, size_t thresh) {
    if (!pol) return;
    pol->memoryThresholdBytes = thresh;
    pol->enableLeakWarnings = true;
    printf("Configured Arena Policy: Threshold=%zu bytes\n", thresh);
}

void printArenaDiagnostics(const MemoryArena* arena) {
    if (!arena) return;
    printf("\n=== Linear Memory Arena Statistics ===\n");
    printf("Total Capacity   : %d KB\n", (int)(ARENA_CAPACITY_BYTES / 1024));
    printf("Current Offset   : %zu bytes\n", arena->offset);
    printf("Allocations Count: %zu\n", arena->allocationCount);
    printf("Requested Bytes  : %zu bytes\n", arena->totalRequestedBytes);
    printf("Memory Utilized  : %.2f%%\n", (100.0 * arena->offset) / ARENA_CAPACITY_BYTES);
    printf("======================================\n");
}


typedef struct {
    size_t highWaterMark;
    size_t allocationFailures;
} ArenaResourceMonitor;

void recordArenaStats(ArenaResourceMonitor* m, size_t currentOffset) {
    if (!m) return;
    if (currentOffset > m->highWaterMark) {
        m->highWaterMark = currentOffset;
    }
}

void printArenaMonitorSummary(const ArenaResourceMonitor* m) {
    if (!m) return;
    printf("Arena Monitor: High-water mark=%zu bytes | Failures=%zu\\n",
           m->highWaterMark, m->allocationFailures);
}

typedef struct {
    char tag[24];
    int blocksTracked;
} MemoryTracker;

void trackBlock(MemoryTracker* t, const char* label, size_t sz) {
    if (!t) return;
    t->blocksTracked++;
    printf("  [ARENA-BLOCK-%02d] Allocated '%s' (%zu bytes)\n", t->blocksTracked, label, sz);
}

void runArenaHeader(void) {
    printf("============================================================\n");
    printf("    C11 EMBEDDED CONTIGUOUS LINEAR MEMORY ARENA             \n");
    printf("    Zero-Fragmentation High-Throughput Chunk Allocator      \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [ARENA-PAGE-SLOT-%02d] Initializing arena virtual chunk %d.\n", k, k);
    }
}

int main(void) {
    runArenaHeader();
    MemoryArena arena;
    arenaInit(&arena);

    MemoryTracker tracker;
    strncpy(tracker.tag, "AST_ARENA", sizeof(tracker.tag) - 1);
    tracker.blocksTracked = 0;

    int* numbers = (int*)arenaAlloc(&arena, 10 * sizeof(int), 4);
    if (numbers) {
        for (int i = 0; i < 10; ++i) numbers[i] = i * 10;
        trackBlock(&tracker, "IntBuffer10", 10 * sizeof(int));
    }

    char* textBuffer = (char*)arenaAllocZero(&arena, 256, 1);
    if (textBuffer) {
        snprintf(textBuffer, 256, "Antigravity Linear Arena Buffer Demonstration");
        trackBlock(&tracker, "TextStringChunk", 256);
    }

    double* matrixRow = (double*)arenaAlloc(&arena, 8 * sizeof(double), 8);
    if (matrixRow) {
        for (int j = 0; j < 8; ++j) matrixRow[j] = j * 3.14159;
        trackBlock(&tracker, "DoubleRow8", 8 * sizeof(double));
    }

    printArenaDiagnostics(&arena);
    arenaReset(&arena);
    printf("Arena successfully reset. Offset is now: %zu\n", arena.offset);
    return 0;
}
