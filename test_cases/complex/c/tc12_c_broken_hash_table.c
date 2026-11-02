#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

// Complex broken C program for self-healing compiler benchmark
// Chained hash table with string keys and integer values
// Contains 3-5 distinct C compilation faults (150-500 LOC)

#define HASH_TABLE_CAPACITY 64

typedef struct HashNode {
    char key[64];
    int value;
    struct HashNode* next;
} HashNode;

typedef struct {
    HashNode* buckets[HASH_TABLE_CAPACITY];
    size_t size;
    size_t collisions;
} HashTable;

typedef struct {
    char tableName[32];
    double loadFactor;
    int maxChainLength;
} TableDiagnostics;

void printTableDiagnostics(const TableDiagnostics* d) {
    if (!d) return;
    printf("[TABLE-DIAG] Table: %s | LoadFactor: %.3f | MaxChain: %d\n",
           d->tableName, d->loadFactor, d->maxChainLength);
}

// ERROR 1: Missing return type on function
hashStringKey(const char* key) {
    if (!key) return 0;
    unsigned long hash = 5381;
    int c;
    while ((c = *key++)) {
        hash = ((hash << 5) + hash) + c;
    }
    return (unsigned int)(hash % HASH_TABLE_CAPACITY);
}

void initHashTable(HashTable* ht) {
    if (!ht) return;
    for (size_t i = 0; i < HASH_TABLE_CAPACITY; ++i) {
        // ERROR 2: Incompatible pointer assignment without cast
        ht->buckets[i] = "string_cannot_be_assigned_to_hashnode";
    }
    ht->size = 0;
    ht->collisions = 0;
}

bool hashInsert(HashTable* ht, const char* key, int value) {
    if (!ht || !key) return false;

    // ERROR 3: Undeclared variable 'htInitialCapacity'
    if (ht->size >= htInitialCapacity) {
        return false;
    }

    unsigned int idx = hashStringKey(key);
    HashNode* curr = ht->buckets[idx];

    while (curr) {
        if (strcmp(curr->key, key) == 0) {
            curr->value = value;
            return true;
        }
        curr = curr->next;
    }

    HashNode* node = (HashNode*)malloc(sizeof(HashNode));
    if (!node) return false;
    strncpy(node->key, key, 63);
    node->key[63] = '\0';
    node->value = value;
    node->next = ht->buckets[idx];

    if (ht->buckets[idx] != NULL) {
        ht->collisions++;
    }

    ht->buckets[idx] = node;
    ht->size++;
    return true;
}

bool hashLookup(const HashTable* ht, const char* key, int* outValue) {
    if (!ht || !key || !outValue) return false;
    unsigned int idx = hashStringKey(key);
    HashNode* curr = ht->buckets[idx];

    while (curr) {
        if (strcmp(curr->key, key) == 0) {
            *outValue = curr->value;
            return true;
        }
        curr = curr->next;
    }
    return false;
}

void printHashTableStats(const HashTable* ht) {
    if (!ht) return;
    printf("\n=== Hash Table Status ===\n");
    printf("Item Count: %zu\n", ht->size);
    printf("Collisions: %zu\n", ht->collisions);
}

void runPreflightTableChecks(void) {
    printf("============================================================\n");
    printf("   C11 HASH TABLE BENCHMARK EVALUATION HARNESS             \n");
    printf("   Multi-Fault Broken Benchmark Fixture (3-5 Faults)        \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [HASH-SLOT-PREFLIGHT-%02d] Checking table bucket slot %d.\n", k, k);
    }
}

int main(void) {
    runPreflightTableChecks();

    HashTable table;
    initHashTable(&table);

    TableDiagnostics diag = {"SYMBOL_TABLE_01", 0.25, 2};
    printTableDiagnostics(&diag);

    hashInsert(&table, "alpha", 100);
    hashInsert(&table, "beta", 200);
    hashInsert(&table, "gamma", 300);

    int val = 0;
    if (hashLookup(&table, "beta", &val)) {
        printf("Lookup 'beta': %d\n", val);
    }

    printHashTableStats(&table);

    // ERROR 4: Calling undefined function
    rehashTableBucketsDynamically(&table);

    return 0;
}

