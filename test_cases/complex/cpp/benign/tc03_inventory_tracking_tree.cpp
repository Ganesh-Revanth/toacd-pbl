#include <iostream>
#include <string>
#include <memory>
#include <vector>
#include <iomanip>
#include <algorithm>
#include <sstream>

template <typename T>
class InventoryNode {
public:
    int itemId;
    std::string itemName;
    T price;
    int stockQuantity;
    int height;
    std::unique_ptr<InventoryNode<T>> left;
    std::unique_ptr<InventoryNode<T>> right;

    InventoryNode(int id, std::string name, T pr, int qty)
        : itemId(id), itemName(std::move(name)), price(pr), stockQuantity(qty),
          height(1), left(nullptr), right(nullptr) {}
};

template <typename T>
class InventoryAVLTree {
private:
    std::unique_ptr<InventoryNode<T>> root;

    int getHeight(const std::unique_ptr<InventoryNode<T>>& node) const {
        return node ? node->height : 0;
    }

    int getBalanceFactor(const std::unique_ptr<InventoryNode<T>>& node) const {
        return node ? getHeight(node->left) - getHeight(node->right) : 0;
    }

    void updateHeight(std::unique_ptr<InventoryNode<T>>& node) {
        if (node) {
            node->height = 1 + std::max(getHeight(node->left), getHeight(node->right));
        }
    }

    std::unique_ptr<InventoryNode<T>> rotateRight(std::unique_ptr<InventoryNode<T>> y) {
        auto x = std::move(y->left);
        y->left = std::move(x->right);
        updateHeight(y);
        x->right = std::move(y);
        updateHeight(x);
        return x;
    }

    std::unique_ptr<InventoryNode<T>> rotateLeft(std::unique_ptr<InventoryNode<T>> x) {
        auto y = std::move(x->right);
        x->right = std::move(y->left);
        updateHeight(x);
        y->left = std::move(x);
        updateHeight(y);
        return y;
    }

    std::unique_ptr<InventoryNode<T>> insertRec(std::unique_ptr<InventoryNode<T>> node, int id, const std::string& name, T price, int qty) {
        if (!node) {
            return std::make_unique<InventoryNode<T>>(id, name, price, qty);
        }

        if (id < node->itemId) {
            node->left = insertRec(std::move(node->left), id, name, price, qty);
        } else if (id > node->itemId) {
            node->right = insertRec(std::move(node->right), id, name, price, qty);
        } else {
            node->stockQuantity += qty;
            node->price = price;
            return node;
        }

        updateHeight(node);
        int balance = getBalanceFactor(node);

        if (balance > 1 && id < node->left->itemId) {
            return rotateRight(std::move(node));
        }
        if (balance < -1 && id > node->right->itemId) {
            return rotateLeft(std::move(node));
        }
        if (balance > 1 && id > node->left->itemId) {
            node->left = rotateLeft(std::move(node->left));
            return rotateRight(std::move(node));
        }
        if (balance < -1 && id < node->right->itemId) {
            node->right = rotateRight(std::move(node->right));
            return rotateLeft(std::move(node));
        }
        return node;
    }

    const InventoryNode<T>* searchRec(const InventoryNode<T>* node, int id) const {
        if (!node || node->itemId == id) return node;
        if (id < node->itemId) return searchRec(node->left.get(), id);
        return searchRec(node->right.get(), id);
    }

    void inOrderRec(const InventoryNode<T>* node, std::vector<const InventoryNode<T>*>& acc) const {
        if (!node) return;
        inOrderRec(node->left.get(), acc);
        acc.push_back(node);
        inOrderRec(node->right.get(), acc);
    }

public:
    InventoryAVLTree() : root(nullptr) {}

    void insert(int id, const std::string& name, T price, int qty) {
        root = insertRec(std::move(root), id, name, price, qty);
    }

    const InventoryNode<T>* find(int id) const {
        return searchRec(root.get(), id);
    }

    bool updateStock(int id, int delta) {
        auto* node = const_cast<InventoryNode<T>*>(find(id));
        if (!node || (node->stockQuantity + delta) < 0) return false;
        node->stockQuantity += delta;
        return true;
    }

    std::vector<const InventoryNode<T>*> getAllSorted() const {
        std::vector<const InventoryNode<T>*> items;
        inOrderRec(root.get(), items);
        return items;
    }

    T computeInventoryValuation() const {
        auto items = getAllSorted();
        T sum = 0;
        for (const auto* it : items) {
            sum += it->price * it->stockQuantity;
        }
        return sum;
    }

    void display() const {
        auto items = getAllSorted();
        std::cout << "\n================= INVENTORY AVL TREE ================\n";
        std::cout << std::setw(8) << "ID" << " | "
                  << std::setw(25) << std::left << "Item Description" << " | "
                  << std::setw(10) << "Unit Price" << " | "
                  << std::setw(8) << "Stock" << "\n";
        std::cout << "-----------------------------------------------------\n";
        for (const auto* it : items) {
            std::cout << std::setw(8) << it->itemId << " | "
                      << std::setw(25) << std::left << it->itemName << " | $"
                      << std::setw(9) << std::fixed << std::setprecision(2) << it->price << " | "
                      << std::setw(8) << it->stockQuantity << "\n";
        }
        std::cout << "=====================================================\n";
    }
};

int main() {
    InventoryAVLTree<double> warehouse;
    warehouse.insert(105, "Titanium Bolts M6", 2.45, 500);
    warehouse.insert(102, "Alloy Hex Nuts M6", 0.85, 1200);
    warehouse.insert(108, "Steel Flange Washers", 0.40, 3000);
    warehouse.insert(101, "Precision Bearings", 14.50, 150);
    warehouse.insert(104, "Drive Belt 250mm", 19.99, 45);
    warehouse.insert(107, "Stepper Motor 12V", 35.00, 80);

    warehouse.display();
    warehouse.updateStock(101, -25);
    warehouse.updateStock(108, 500);

    std::cout << "Total Inventory Valuation: $" << warehouse.computeInventoryValuation() << "\n";
    return 0;
}
