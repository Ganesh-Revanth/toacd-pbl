#include <iostream>
#include <string>
#include <list>
#include <vector>
#include <unordered_map>
#include <optional>
#include <stdexcept>
#include <iomanip>
#include <chrono>

template <typename Key, typename Value>
class GenericLruCache {
public:
    using KeyValuePair = std::pair<Key, Value>;
    using ListIterator = typename std::list<KeyValuePair>::iterator;

private:
    size_t capacity;
    std::list<KeyValuePair> itemsList;
    std::unordered_map<Key, ListIterator> lookupTable;
    size_t hitCount;
    size_t missCount;

public:
    explicit GenericLruCache(size_t cap)
        : capacity(cap), hitCount(0), missCount(0) {
        if (capacity == 0) throw std::invalid_argument("Capacity must be positive");
    }

    void put(const Key& key, const Value& val) {
        auto it = lookupTable.find(key);
        if (it != lookupTable.end()) {
            itemsList.erase(it->second);
            lookupTable.erase(it);
        } else if (lookupTable.size() >= capacity) {
            auto oldest = itemsList.back();
            lookupTable.erase(oldest.first);
            itemsList.pop_back();
        }

        itemsList.emplace_front(key, val);
        lookupTable[key] = itemsList.begin();
    }

    std::optional<Value> get(const Key& key) {
        auto it = lookupTable.find(key);
        if (it == lookupTable.end()) {
            missCount++;
            return std::nullopt;
        }

        hitCount++;
        Value foundVal = it->second->second;
        itemsList.erase(it->second);
        itemsList.emplace_front(key, foundVal);
        lookupTable[key] = itemsList.begin();
        return foundVal;
    }

    std::optional<Value> peek(const Key& key) const {
        auto it = lookupTable.find(key);
        if (it == lookupTable.end()) return std::nullopt;
        return it->second->second;
    }

    bool remove(const Key& key) {
        auto it = lookupTable.find(key);
        if (it == lookupTable.end()) return false;
        itemsList.erase(it->second);
        lookupTable.erase(it);
        return true;
    }

    void clear() {
        itemsList.clear();
        lookupTable.clear();
        hitCount = 0;
        missCount = 0;
    }

    std::vector<Key> getKeys() const {
        std::vector<Key> keys;
        for (const auto& pair : itemsList) {
            keys.push_back(pair.first);
        }
        return keys;
    }

    bool contains(const Key& key) const {
        return lookupTable.find(key) != lookupTable.end();
    }

    size_t size() const { return lookupTable.size(); }
    size_t getCapacity() const { return capacity; }
    size_t getHits() const { return hitCount; }
    size_t getMisses() const { return missCount; }

    double getHitRatio() const {
        size_t total = hitCount + missCount;
        return (total > 0) ? (static_cast<double>(hitCount) / total) : 0.0;
    }

    void printState() const {
        std::cout << "\n================ LRU CACHE STATE ================\n";
        std::cout << "Capacity : " << capacity << " | Current Size: " << lookupTable.size() << "\n";
        std::cout << "Hits     : " << hitCount << " | Misses: " << missCount
                  << " | Hit Ratio: " << std::fixed << std::setprecision(1) << (getHitRatio() * 100.0) << "%\n";
        std::cout << "MRU -> LRU Chain:\n";
        for (const auto& pair : itemsList) {
            std::cout << "  [" << pair.first << " : " << pair.second << "]\n";
        }
        std::cout << "=================================================\n";
    }
};

int main() {
    GenericLruCache<std::string, int> cache(4);

    cache.put("kernel_ast", 101);
    cache.put("type_env", 202);
    cache.put("symbol_table", 303);
    cache.put("cfg_graph", 404);

    cache.printState();

    auto val1 = cache.get("kernel_ast"); // Hit, brings kernel_ast to front
    std::cout << "Access 'kernel_ast': " << (val1.has_value() ? std::to_string(val1.value()) : "MISS") << "\n";

    cache.put("bytecode_bin", 505); // Evicts type_env (oldest)
    cache.printState();

    auto val2 = cache.get("type_env"); // Miss
    std::cout << "Access 'type_env': " << (val2.has_value() ? std::to_string(val2.value()) : "MISS") << "\n";

    cache.put("ssa_ir", 606); // Evicts symbol_table
    cache.printState();

    std::cout << "\nPeek 'ssa_ir' without reordering: ";
    auto peekVal = cache.peek("ssa_ir");
    std::cout << (peekVal.has_value() ? std::to_string(peekVal.value()) : "MISS") << "\n";

    std::cout << "Removing 'cfg_graph': " << (cache.remove("cfg_graph") ? "SUCCESS" : "NOT_FOUND") << "\n";
    cache.printState();

    auto activeKeys = cache.getKeys();
    std::cout << "Active Cache Keys: ";
    for (const auto& k : activeKeys) std::cout << "[" << k << "] ";
    std::cout << "\n";

    return 0;
}
