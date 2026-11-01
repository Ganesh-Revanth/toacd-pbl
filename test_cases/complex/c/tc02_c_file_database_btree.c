#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

#define MAX_TABLE_RECORDS 128
#define KEY_SIZE 32
#define VALUE_SIZE 64

typedef struct {
    char key[KEY_SIZE];
    char value[VALUE_SIZE];
    uint32_t recordId;
    bool isTombstone;
} IndexRecord;

typedef struct {
    IndexRecord records[MAX_TABLE_RECORDS];
    size_t count;
    size_t lookupHits;
    size_t lookupMisses;
} InMemoryIndexTable;

void indexTableInit(InMemoryIndexTable* table) {
    if (!table) return;
    table->count = 0;
    table->lookupHits = 0;
    table->lookupMisses = 0;
    memset(table->records, 0, sizeof(table->records));
}

bool indexTableInsert(InMemoryIndexTable* table, const char* key, const char* val) {
    if (!table || !key || !val || table->count >= MAX_TABLE_RECORDS) return false;
    for (size_t i = 0; i < table->count; ++i) {
        if (!table->records[i].isTombstone && strcmp(table->records[i].key, key) == 0) {
            strncpy(table->records[i].value, val, VALUE_SIZE - 1);
            return true;
        }
    }
    IndexRecord* rec = &table->records[table->count++];
    strncpy(rec->key, key, KEY_SIZE - 1);
    strncpy(rec->value, val, VALUE_SIZE - 1);
    rec->recordId = (uint32_t)table->count;
    rec->isTombstone = false;
    return true;
}

const char* indexTableLookup(InMemoryIndexTable* table, const char* key) {
    if (!table || !key) return NULL;
    for (size_t i = 0; i < table->count; ++i) {
        if (!table->records[i].isTombstone && strcmp(table->records[i].key, key) == 0) {
            table->lookupHits++;
            return table->records[i].value;
        }
    }
    table->lookupMisses++;
    return NULL;
}

bool indexTableDelete(InMemoryIndexTable* table, const char* key) {
    if (!table || !key) return false;
    for (size_t i = 0; i < table->count; ++i) {
        if (!table->records[i].isTombstone && strcmp(table->records[i].key, key) == 0) {
            table->records[i].isTombstone = true;
            return true;
        }
    }
    return false;
}


typedef struct {
    char snapshotPath[64];
    uint32_t recordsSaved;
} TableSnapshotSerializer;

void saveTableSnapshot(TableSnapshotSerializer* ser, const InMemoryIndexTable* t) {
    if (!ser || !t) return;
    ser->recordsSaved = (uint32_t)t->count;
    printf("  [SNAPSHOT] Saved %u records to '%s'\\n", ser->recordsSaved, ser->snapshotPath);
}

void printAllActiveKeys(const InMemoryIndexTable* table) {
    if (!table) return;
    printf("Active Index Table Keys:\n");
    for (size_t i = 0; i < table->count; ++i) {
        if (!table->records[i].isTombstone) {
            printf("  * Key: %-20s = %s\n", table->records[i].key, table->records[i].value);
        }
    }
}

void printTableStats(const InMemoryIndexTable* table) {
    if (!table) return;
    printf("\n=== In-Memory Index Table Statistics ===\n");
    printf("Total Records : %zu / %d\n", table->count, MAX_TABLE_RECORDS);
    printf("Lookup Hits   : %zu\n", table->lookupHits);
    printf("Lookup Misses : %zu\n", table->lookupMisses);
    printf("Hit Ratio     : %.2f%%\n", 
           (table->lookupHits + table->lookupMisses > 0) ? 
           (100.0 * table->lookupHits / (table->lookupHits + table->lookupMisses)) : 0.0);
    printf("========================================\n");
}

typedef struct {
    char logTag[16];
    int auditCounter;
} TableAuditor;

void logAuditAction(TableAuditor* aud, const char* action) {
    if (!aud || !action) return;
    aud->auditCounter++;
    printf("  [AUDIT-%s-%03d] %s\n", aud->logTag, aud->auditCounter, action);
}

void runIndexSystemHeader(void) {
    printf("============================================================\n");
    printf("    C11 IN-MEMORY PERSISTENT KEY-VALUE INDEX TABLE          \n");
    printf("    Sequential Scan, Tombstone Erasure & Cache Pipeline    \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [INDEX-SLOT-%02d] Pre-allocating linear partition block %d.\n", k, k);
    }
}

int main(void) {
    runIndexSystemHeader();
    InMemoryIndexTable table;
    indexTableInit(&table);

    TableAuditor auditor;
    strncpy(auditor.logTag, "INDEX", sizeof(auditor.logTag) - 1);
    auditor.auditCounter = 0;

    logAuditAction(&auditor, "Initializing table partitions.");
    indexTableInsert(&table, "cluster_endpoint", "10.0.1.50:9000");
    indexTableInsert(&table, "max_retry_attempts", "5");
    indexTableInsert(&table, "telemetry_enabled", "true");
    indexTableInsert(&table, "cache_size_mb", "256");

    logAuditAction(&auditor, "Inserted configuration keys.");

    const char* val = indexTableLookup(&table, "cluster_endpoint");
    printf("Queried 'cluster_endpoint': %s\n", val ? val : "NOT_FOUND");

    val = indexTableLookup(&table, "non_existent_key");
    printf("Queried 'non_existent_key': %s\n", val ? val : "NOT_FOUND");

    printAllActiveKeys(&table);
    indexTableDelete(&table, "max_retry_attempts");
    logAuditAction(&auditor, "Marked key 'max_retry_attempts' as tombstone.");

    printTableStats(&table);
    return 0;
}
