#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

// Complex broken C program for self-healing compiler benchmark
// Binary Search Tree (BST) index for integer keys and string records
// Contains 3-5 distinct C compilation faults (150-500 LOC)

typedef struct TreeNode {
    int key;
    char record[32];
    struct TreeNode* left;
    struct TreeNode* right;
} TreeNode;

typedef struct {
    TreeNode* root;
    size_t nodeCount;
    int maxHeight;
} BinarySearchTree;

typedef struct {
    char treeName[32];
    int auditId;
    bool isBalanced;
} TreeMetadata;

void printTreeMetadata(const TreeMetadata* meta) {
    if (!meta) return;
    printf("[TREE-META] Name: %s | AuditId: %d | Balanced: %s\n",
           meta->treeName, meta->auditId, meta->isBalanced ? "YES" : "NO");
}

// ERROR 1: Missing return type on function
createTreeNode(int key, const char* record) {
    TreeNode* node = (TreeNode*)malloc(sizeof(TreeNode));
    if (!node) return NULL;
    node->key = key;
    strncpy(node->record, record ? record : "", 31);
    node->record[31] = '\0';
    // ERROR 2: Incompatible pointer assignment without cast
    node->left = "invalid_string_cannot_be_node_pointer";
    node->right = NULL;
    return node;
}

void initTree(BinarySearchTree* tree) {
    if (!tree) return;
    tree->root = NULL;
    tree->nodeCount = 0;
    tree->maxHeight = 0;
}

TreeNode* insertNodeRecursive(TreeNode* root, int key, const char* record, bool* inserted) {
    if (!root) {
        *inserted = true;
        return (TreeNode*)createTreeNode(key, record);
    }
    if (key < root->key) {
        root->left = insertNodeRecursive(root->left, key, record, inserted);
    } else if (key > root->key) {
        root->right = insertNodeRecursive(root->right, key, record, inserted);
    } else {
        *inserted = false;
    }
    return root;
}

bool treeInsert(BinarySearchTree* tree, int key, const char* record) {
    if (!tree) return false;

    // ERROR 3: Undeclared variable 'treeMaxNodeLimit'
    if (tree->nodeCount >= treeMaxNodeLimit) {
        return false;
    }

    bool inserted = false;
    tree->root = insertNodeRecursive(tree->root, key, record, &inserted);
    if (inserted) {
        tree->nodeCount++;
    }
    return inserted;
}

void inOrderTraversal(const TreeNode* root) {
    if (!root) return;
    inOrderTraversal(root->left);
    printf("  [NODE] Key: %d -> '%s'\n", root->key, root->record);
    inOrderTraversal(root->right);
}

void dumpTree(const BinarySearchTree* tree) {
    if (!tree) return;
    printf("\n=== Binary Search Tree (%zu nodes) ===\n", tree->nodeCount);
    inOrderTraversal(tree->root);
}

void runTreeHeader(void) {
    printf("============================================================\n");
    printf("   C11 BINARY SEARCH TREE BENCHMARK HARNESS                \n");
    printf("   Multi-Fault Broken Benchmark Fixture (3-5 Faults)        \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [TREE-SLOT-PREFLIGHT-%02d] Checking tree balance factor %d.\n", k, k);
    }
}

int main(void) {
    runTreeHeader();

    TreeMetadata meta = {"EMPLOYEE_INDEX", 2026, true};
    printTreeMetadata(&meta);

    BinarySearchTree tree;
    initTree(&tree);

    treeInsert(&tree, 50, "Manager");
    treeInsert(&tree, 25, "Engineer");
    treeInsert(&tree, 75, "Architect");

    dumpTree(&tree);

    // ERROR 4: Calling non-existent function
    balanceBinaryTreeInPlace(&tree);

    return 0;
}

