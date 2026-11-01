#include <iostream>
#include <string>
#include <memory>
#include <vector>
#include <queue>
#include <iomanip>

template <typename Key, typename Value>
class GenericBST {
private:
    struct Node {
        Key key;
        Value value;
        std::unique_ptr<Node> left;
        std::unique_ptr<Node> right;

        Node(Key k, Value v) : key(std::move(k)), value(std::move(v)), left(nullptr), right(nullptr) {}
    };

    std::unique_ptr<Node> root;
    size_t nodeCount;

    void insertRec(std::unique_ptr<Node>& node, Key k, Value v) {
        if (!node) {
            node = std::make_unique<Node>(std::move(k), std::move(v));
            nodeCount++;
            return;
        }
        if (k < node->key) {
            insertRec(node->left, std::move(k), std::move(v));
        } else if (k > node->key) {
            insertRec(node->right, std::move(k), std::move(v));
        } else {
            node->value = std::move(v); // update existing key
        }
    }

    const Value* findRec(const Node* node, const Key& k) const {
        if (!node) return nullptr;
        if (k == node->key) return &node->value;
        if (k < node->key) return findRec(node->left.get(), k);
        return findRec(node->right.get(), k);
    }

    int heightRec(const Node* node) const {
        if (!node) return 0;
        return 1 + std::max(heightRec(node->left.get()), heightRec(node->right.get()));
    }

    std::unique_ptr<Node> removeRec(std::unique_ptr<Node> node, const Key& k) {
        if (!node) return nullptr;

        if (k < node->key) {
            node->left = removeRec(std::move(node->left), k);
        } else if (k > node->key) {
            node->right = removeRec(std::move(node->right), k);
        } else {
            // Case 1 & 2: 0 or 1 child
            if (!node->left) {
                nodeCount--;
                return std::move(node->right);
            }
            if (!node->right) {
                nodeCount--;
                return std::move(node->left);
            }

            // Case 3: 2 children. Find min node in right subtree
            Node* successor = node->right.get();
            while (successor->left) {
                successor = successor->left.get();
            }
            node->key = successor->key;
            node->value = successor->value;
            node->right = removeRec(std::move(node->right), successor->key);
        }
        return node;
    }

    void inOrderRec(const Node* node, std::vector<std::pair<Key, Value>>& out) const {
        if (!node) return;
        inOrderRec(node->left.get(), out);
        out.emplace_back(node->key, node->value);
        inOrderRec(node->right.get(), out);
    }

public:
    GenericBST() : root(nullptr), nodeCount(0) {}

    void insert(Key k, Value v) {
        insertRec(root, std::move(k), std::move(v));
    }

    const Value* find(const Key& k) const {
        return findRec(root.get(), k);
    }

    bool remove(const Key& k) {
        size_t initial = nodeCount;
        root = removeRec(std::move(root), k);
        return nodeCount < initial;
    }

    int getHeight() const {
        return heightRec(root.get());
    }

    size_t size() const { return nodeCount; }

    std::vector<std::pair<Key, Value>> getInOrderTraversal() const {
        std::vector<std::pair<Key, Value>> result;
        inOrderRec(root.get(), result);
        return result;
    }

    std::vector<Key> getLevelOrderKeys() const {
        std::vector<Key> keys;
        if (!root) return keys;

        std::queue<const Node*> q;
        q.push(root.get());

        while (!q.empty()) {
            const Node* curr = q.front();
            q.pop();
            keys.push_back(curr->key);
            if (curr->left) q.push(curr->left.get());
            if (curr->right) q.push(curr->right.get());
        }
        return keys;
    }
};

int main() {
    GenericBST<int, std::string> bst;
    bst.insert(50, "Root Node");
    bst.insert(30, "Left Subtree");
    bst.insert(70, "Right Subtree");
    bst.insert(20, "Leaf 20");
    bst.insert(40, "Leaf 40");
    bst.insert(60, "Leaf 60");
    bst.insert(80, "Leaf 80");

    std::cout << "================ GENERIC BST TEMPLATE ================\n";
    std::cout << "Total Nodes: " << bst.size() << " | Tree Height: " << bst.getHeight() << "\n";

    auto pairs = bst.getInOrderTraversal();
    std::cout << "In-Order Sorted Traversal:\n";
    for (const auto& p : pairs) {
        std::cout << "  [" << p.first << "] -> " << p.second << "\n";
    }

    auto levelKeys = bst.getLevelOrderKeys();
    std::cout << "Level-Order Keys: ";
    for (int k : levelKeys) std::cout << k << " ";
    std::cout << "\n";

    const auto* found = bst.find(40);
    std::cout << "Lookup key 40: " << (found ? *found : "NOT_FOUND") << "\n";

    std::cout << "\nRemoving Key 30 (Node with 2 children):\n";
    bst.remove(30);
    std::cout << "Remaining Nodes: " << bst.size() << " | Tree Height: " << bst.getHeight() << "\n";
    std::cout << "Updated In-Order Traversal:\n";
    for (const auto& p : bst.getInOrderTraversal()) {
        std::cout << "  [" << p.first << "] -> " << p.second << "\n";
    }

    return 0;
}
