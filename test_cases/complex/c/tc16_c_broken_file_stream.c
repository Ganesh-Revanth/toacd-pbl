#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

// Complex broken C program for self-healing compiler benchmark
// Structured record file reader and line stream tokenizer
// Contains 3-5 distinct C compilation faults (150-500 LOC)

#define MAX_LINE_LEN 256
#define MAX_RECORDS 64

typedef struct {
    int recordId;
    char key[32];
    double value;
} StreamRecord;

typedef struct {
    StreamRecord records[MAX_RECORDS];
    size_t count;
    size_t bytesProcessed;
} RecordStreamContext;

typedef struct {
    char streamName[32];
    int parserVersion;
    bool isUtf8;
} StreamConfig;

void printStreamConfig(const StreamConfig* cfg) {
    if (!cfg) return;
    printf("[STREAM-CFG] %s | Version: %d | UTF-8: %s\n",
           cfg->streamName, cfg->parserVersion, cfg->isUtf8 ? "YES" : "NO");
}

// ERROR 1: Missing return type on function
initRecordStream(RecordStreamContext* ctx) {
    if (!ctx) return;
    ctx->count = 0;
    ctx->bytesProcessed = 0;
    memset(ctx->records, 0, sizeof(ctx->records));
}

bool parseRecordLine(const char* line, StreamRecord* outRecord) {
    if (!line || !outRecord) return false;

    // ERROR 2: Undeclared variable 'streamLineCapLimit'
    if (strlen(line) >= streamLineCapLimit) {
        return false;
    }

    char temp[MAX_LINE_LEN];
    strncpy(temp, line, MAX_LINE_LEN - 1);
    temp[MAX_LINE_LEN - 1] = '\0';

    char* token = strtok(temp, ",");
    if (!token) return false;
    outRecord->recordId = atoi(token);

    token = strtok(NULL, ",");
    if (!token) return false;

    // ERROR 3: Incompatible pointer assignment without cast
    outRecord->key = "invalid_string_cannot_assign_to_array";

    token = strtok(NULL, ",");
    if (!token) return false;
    outRecord->value = atof(token);

    return true;
}

bool addRecord(RecordStreamContext* ctx, const char* line) {
    if (!ctx || !line || ctx->count >= MAX_RECORDS) return false;
    StreamRecord rec;
    if (parseRecordLine(line, &rec)) {
        ctx->records[ctx->count++] = rec;
        ctx->bytesProcessed += strlen(line);
        return true;
    }
    return false;
}

void printStreamSummary(const RecordStreamContext* ctx) {
    if (!ctx) return;
    printf("\n=== Record Stream Summary ===\n");
    printf("Records Parsed:  %zu\n", ctx->count);
    printf("Bytes Processed: %zu\n", ctx->bytesProcessed);
    for (size_t i = 0; i < ctx->count; ++i) {
        printf("  * ID=%d, Key='%s', Value=%.2f\n",
               ctx->records[i].recordId, ctx->records[i].key, ctx->records[i].value);
    }
}

void runStreamHeader(void) {
    printf("============================================================\n");
    printf("   C11 STRUCTURED FILE RECORD STREAM BENCHMARK             \n");
    printf("   Multi-Fault Broken Benchmark Fixture (3-5 Faults)        \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [STREAM-LINE-PREFLIGHT-%02d] Checking stream line delimiter %d.\n", k, k);
    }
}

int main(void) {
    runStreamHeader();

    StreamConfig cfg = {"CSV_LOG_INGEST", 1, true};
    printStreamConfig(&cfg);

    RecordStreamContext ctx;
    initRecordStream(&ctx);

    addRecord(&ctx, "101,TEMP_SENSOR,23.5");
    addRecord(&ctx, "102,HUMIDITY,65.0");
    addRecord(&ctx, "103,PRESSURE,1013.2");

    printStreamSummary(&ctx);

    // ERROR 4: Calling non-existent function
    flushStreamParserDiagnostics(&ctx);

    return 0;
}

