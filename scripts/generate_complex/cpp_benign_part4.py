"""
scripts/generate_complex/cpp_benign_part4.py
--------------------------------------------
Generates C++ benign complex fixtures 31 through 40.
Each fixture: 150-500 lines, compiles cleanly with g++ -std=c++17.
"""

from pathlib import Path
from typing import Dict, Tuple
from .utils import validate_and_write


def generate_all(base_dir: Path) -> Dict[str, Tuple[bool, int, str]]:
    results = {}

    # ── TC31: Sparse Matrix Linked List ───────────────────────────────────────
    tc31 = r'''#include <iostream>
#include <vector>
#include <memory>
#include <iomanip>
#include <stdexcept>
#include <cmath>

struct SparseElementNode {
    size_t colIndex;
    double value;
    std::shared_ptr<SparseElementNode> next;

    SparseElementNode(size_t col, double val)
        : colIndex(col), value(val), next(nullptr) {}
};

class LinkedListSparseMatrix {
private:
    size_t rowCount;
    size_t colCount;
    std::vector<std::shared_ptr<SparseElementNode>> rowHeads;

public:
    LinkedListSparseMatrix(size_t rows, size_t cols)
        : rowCount(rows), colCount(cols), rowHeads(rows, nullptr) {}

    void insert(size_t r, size_t c, double val) {
        if (r >= rowCount || c >= colCount) throw std::out_of_range("Matrix bounds exceeded");
        if (std::abs(val) < 1e-9) return; // Ignore zero entries

        auto newNode = std::make_shared<SparseElementNode>(c, val);
        if (!rowHeads[r] || c < rowHeads[r]->colIndex) {
            newNode->next = rowHeads[r];
            rowHeads[r] = newNode;
            return;
        }

        auto curr = rowHeads[r];
        while (curr->next && curr->next->colIndex < c) {
            curr = curr->next;
        }

        if (curr->colIndex == c) {
            curr->value = val; // Overwrite
        } else if (curr->next && curr->next->colIndex == c) {
            curr->next->value = val;
        } else {
            newNode->next = curr->next;
            curr->next = newNode;
        }
    }

    double get(size_t r, size_t c) const {
        if (r >= rowCount || c >= colCount) throw std::out_of_range("Matrix bounds exceeded");
        auto curr = rowHeads[r];
        while (curr) {
            if (curr->colIndex == c) return curr->value;
            if (curr->colIndex > c) break;
            curr = curr->next;
        }
        return 0.0;
    }

    std::vector<double> multiplyVector(const std::vector<double>& vec) const {
        if (vec.size() != colCount) throw std::invalid_argument("Vector size must equal matrix columns");
        std::vector<double> result(rowCount, 0.0);

        for (size_t r = 0; r < rowCount; ++r) {
            auto curr = rowHeads[r];
            double sum = 0.0;
            while (curr) {
                sum += curr->value * vec[curr->colIndex];
                curr = curr->next;
            }
            result[r] = sum;
        }
        return result;
    }

    size_t nonZeroCount() const {
        size_t count = 0;
        for (size_t r = 0; r < rowCount; ++r) {
            auto curr = rowHeads[r];
            while (curr) {
                count++;
                curr = curr->next;
            }
        }
        return count;
    }

    LinkedListSparseMatrix transpose() const {
        LinkedListSparseMatrix trans(colCount, rowCount);
        for (size_t r = 0; r < rowCount; ++r) {
            auto curr = rowHeads[r];
            while (curr) {
                trans.insert(curr->colIndex, r, curr->value);
                curr = curr->next;
            }
        }
        return trans;
    }

    LinkedListSparseMatrix add(const LinkedListSparseMatrix& other) const {
        if (rowCount != other.rowCount || colCount != other.colCount) {
            throw std::invalid_argument("Matrix dimensions must match for addition");
        }
        LinkedListSparseMatrix result(rowCount, colCount);
        for (size_t r = 0; r < rowCount; ++r) {
            for (size_t c = 0; c < colCount; ++c) {
                double sum = get(r, c) + other.get(r, c);
                if (std::abs(sum) > 1e-9) {
                    result.insert(r, c, sum);
                }
            }
        }
        return result;
    }

    double computeSparsity() const {
        size_t total = rowCount * colCount;
        return (total > 0) ? (1.0 - (static_cast<double>(nonZeroCount()) / total)) : 1.0;
    }

    void printDense(const std::string& label = "") const {
        if (!label.empty()) std::cout << "--- " << label << " ---\n";
        for (size_t r = 0; r < rowCount; ++r) {
            std::cout << "[ ";
            for (size_t c = 0; c < colCount; ++c) {
                std::cout << std::setw(6) << std::fixed << std::setprecision(1) << get(r, c) << " ";
            }
            std::cout << "]\n";
        }
    }
};

int main() {
    LinkedListSparseMatrix sp(5, 5);
    sp.insert(0, 1, 4.5);
    sp.insert(0, 4, 1.2);
    sp.insert(1, 1, 8.0);
    sp.insert(2, 3, 3.7);
    sp.insert(4, 0, 9.1);
    sp.insert(4, 4, 6.4);

    sp.printDense("5x5 Sparse Matrix");
    std::cout << "Non-Zero Elements: " << sp.nonZeroCount() << "\n";
    std::cout << "Matrix Sparsity  : " << std::fixed << std::setprecision(2)
              << (sp.computeSparsity() * 100.0) << "%\n";

    std::vector<double> inputVec = {1.0, 2.0, 3.0, 4.0, 5.0};
    auto outVec = sp.multiplyVector(inputVec);

    std::cout << "\nVector Multiplication (Sp * [1, 2, 3, 4, 5]^T):\nResult: [ ";
    for (double val : outVec) std::cout << val << " ";
    std::cout << "]\n";

    auto transposed = sp.transpose();
    transposed.printDense("Transposed Sparse Matrix");

    auto sumMat = sp.add(transposed);
    sumMat.printDense("Symmetric Sum (Sp + Sp^T)");

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc31_sparse_matrix_linked_list.cpp", tc31, expect_compile=True)
    results["tc31_sparse_matrix_linked_list.cpp"] = (res, count, msg)

    # ── TC32: Plugin Registry Loader ──────────────────────────────────────────
    tc32 = r'''#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <sstream>
#include <iomanip>

enum class PluginLifecycleState { UNLOADED, INITIALIZED, ACTIVE, SUSPENDED, TERMINATED };

class IPluginComponent {
public:
    virtual ~IPluginComponent() = default;
    virtual std::string getPluginId() const = 0;
    virtual std::string getVersion() const = 0;
    virtual bool onInitialize() = 0;
    virtual void onExecute() = 0;
    virtual void onShutdown() = 0;
};

class LexerOptimizerPlugin : public IPluginComponent {
public:
    std::string getPluginId() const override { return "plugin.lexer.optimizer"; }
    std::string getVersion() const override { return "2.4.1"; }

    bool onInitialize() override {
        std::cout << "  [" << getPluginId() << "] Fast regex lookup tables compiled.\n";
        return true;
    }

    void onExecute() override {
        std::cout << "  [" << getPluginId() << "] Token streaming buffer optimized.\n";
    }

    void onShutdown() override {
        std::cout << "  [" << getPluginId() << "] Flushed scratch state.\n";
    }
};

class AstHealerPlugin : public IPluginComponent {
public:
    std::string getPluginId() const override { return "plugin.ast.healer"; }
    std::string getVersion() const override { return "1.0.8"; }

    bool onInitialize() override {
        std::cout << "  [" << getPluginId() << "] Heuristic rules loaded.\n";
        return true;
    }

    void onExecute() override {
        std::cout << "  [" << getPluginId() << "] Synthesizing repair candidate patch.\n";
    }

    void onShutdown() override {
        std::cout << "  [" << getPluginId() << "] Healer plugin resources released.\n";
    }
};

class PluginRegistryEngine {
private:
    struct PluginDescriptor {
        std::shared_ptr<IPluginComponent> instance;
        PluginLifecycleState state;
    };

    std::map<std::string, PluginDescriptor> registry;

public:
    bool registerPlugin(std::shared_ptr<IPluginComponent> plugin) {
        if (!plugin) return false;
        std::string id = plugin->getPluginId();
        if (registry.find(id) != registry.end()) return false;

        registry[id] = {std::move(plugin), PluginLifecycleState::UNLOADED};
        return true;
    }

    bool initializePlugin(const std::string& id) {
        auto it = registry.find(id);
        if (it == registry.end() || it->second.state != PluginLifecycleState::UNLOADED) return false;

        if (it->second.instance->onInitialize()) {
            it->second.state = PluginLifecycleState::INITIALIZED;
            return true;
        }
        return false;
    }

    void executeAllActive() {
        for (auto& pair : registry) {
            if (pair.second.state == PluginLifecycleState::INITIALIZED ||
                pair.second.state == PluginLifecycleState::ACTIVE) {
                pair.second.instance->onExecute();
                pair.second.state = PluginLifecycleState::ACTIVE;
            }
        }
    }

    void shutdownAll() {
        for (auto& pair : registry) {
            pair.second.instance->onShutdown();
            pair.second.state = PluginLifecycleState::TERMINATED;
        }
    }

    void printRegistryStatus() const {
        std::cout << "\n================ PLUGIN REGISTRY STATUS ================\n";
        for (const auto& pair : registry) {
            std::cout << "Plugin: " << std::setw(25) << std::left << pair.first
                      << " | Ver: " << std::setw(8) << pair.second.instance->getVersion()
                      << " | State: " << stateToString(pair.second.state) << "\n";
        }
        std::cout << "========================================================\n";
    }

private:
    static const char* stateToString(PluginLifecycleState s) {
        switch (s) {
            case PluginLifecycleState::UNLOADED:    return "UNLOADED";
            case PluginLifecycleState::INITIALIZED: return "INITIALIZED";
            case PluginLifecycleState::ACTIVE:      return "ACTIVE";
            case PluginLifecycleState::SUSPENDED:   return "SUSPENDED";
            case PluginLifecycleState::TERMINATED:  return "TERMINATED";
            default: return "UNKNOWN";
        }
    }
};

int main() {
    PluginRegistryEngine registry;
    registry.registerPlugin(std::make_shared<LexerOptimizerPlugin>());
    registry.registerPlugin(std::make_shared<AstHealerPlugin>());

    registry.printRegistryStatus();

    std::cout << "\nInitializing Registered Extensions:\n";
    registry.initializePlugin("plugin.lexer.optimizer");
    registry.initializePlugin("plugin.ast.healer");
    registry.printRegistryStatus();

    std::cout << "\nExecuting Active Extensions:\n";
    registry.executeAllActive();
    registry.printRegistryStatus();

    std::cout << "\nShutting Down Extension Framework:\n";
    registry.shutdownAll();
    registry.printRegistryStatus();

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc32_plugin_registry_loader.cpp", tc32, expect_compile=True)
    results["tc32_plugin_registry_loader.cpp"] = (res, count, msg)

    # ── TC33: Circular Ring Buffer ────────────────────────────────────────────
    tc33 = r'''#include <iostream>
#include <vector>
#include <mutex>
#include <condition_variable>
#include <thread>
#include <chrono>
#include <iomanip>

template <typename T>
class ThreadSafeRingBuffer {
private:
    std::vector<T> buffer;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
    std::mutex bufferMutex;
    std::condition_variable cvNotFull;
    std::condition_variable cvNotEmpty;
    bool isClosed;

public:
    explicit ThreadSafeRingBuffer(size_t cap)
        : buffer(cap), capacity(cap), head(0), tail(0), count(0), isClosed(false) {}

    ~ThreadSafeRingBuffer() {
        close();
    }

    bool push(T item) {
        std::unique_lock<std::mutex> lock(bufferMutex);
        cvNotFull.wait(lock, [this]() {
            return count < capacity || isClosed;
        });

        if (isClosed) return false;

        buffer[tail] = std::move(item);
        tail = (tail + 1) % capacity;
        count++;

        cvNotEmpty.notify_one();
        return true;
    }

    bool pop(T& outItem) {
        std::unique_lock<std::mutex> lock(bufferMutex);
        cvNotEmpty.wait(lock, [this]() {
            return count > 0 || isClosed;
        });

        if (count == 0 && isClosed) return false;

        outItem = std::move(buffer[head]);
        head = (head + 1) % capacity;
        count--;

        cvNotFull.notify_one();
        return true;
    }

    size_t pushBatch(const std::vector<T>& items) {
        std::unique_lock<std::mutex> lock(bufferMutex);
        size_t pushed = 0;
        for (const auto& item : items) {
            if (count >= capacity || isClosed) break;
            buffer[tail] = item;
            tail = (tail + 1) % capacity;
            count++;
            pushed++;
        }
        if (pushed > 0) cvNotEmpty.notify_all();
        return pushed;
    }

    std::vector<T> popBatch(size_t maxItems) {
        std::unique_lock<std::mutex> lock(bufferMutex);
        std::vector<T> popped;
        while (popped.size() < maxItems && count > 0) {
            popped.push_back(std::move(buffer[head]));
            head = (head + 1) % capacity;
            count--;
        }
        if (!popped.empty()) cvNotFull.notify_all();
        return popped;
    }

    bool isBufferFull() {
        std::lock_guard<std::mutex> lock(bufferMutex);
        return count >= capacity;
    }

    bool isBufferEmpty() {
        std::lock_guard<std::mutex> lock(bufferMutex);
        return count == 0;
    }

    void close() {
        {
            std::lock_guard<std::mutex> lock(bufferMutex);
            isClosed = true;
        }
        cvNotFull.notify_all();
        cvNotEmpty.notify_all();
    }

    size_t size() {
        std::lock_guard<std::mutex> lock(bufferMutex);
        return count;
    }
};

int main() {
    ThreadSafeRingBuffer<int> ring(8);

    std::thread producer([&ring]() {
        for (int i = 1; i <= 20; ++i) {
            ring.push(i * 10);
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        ring.close();
    });

    std::thread consumer([&ring]() {
        int val;
        while (ring.pop(val)) {
            std::cout << "Consumed: " << val << "\n";
        }
    });

    producer.join();
    consumer.join();

    std::cout << "Ring Buffer Basic Pipeline Completed.\n";

    std::cout << "\nTesting Batch Operations on Secondary Ring:\n";
    ThreadSafeRingBuffer<std::string> batchRing(16);
    std::vector<std::string> messages = {"MSG_01", "MSG_02", "MSG_03", "MSG_04", "MSG_05"};
    size_t pushedCount = batchRing.pushBatch(messages);
    std::cout << "Pushed batch of " << pushedCount << " messages.\n";

    auto retrieved = batchRing.popBatch(3);
    std::cout << "Retrieved batch of " << retrieved.size() << " items:\n";
    for (const auto& m : retrieved) std::cout << "  * " << m << "\n";

    std::cout << "Remaining in ring buffer: " << batchRing.size() << " items.\n";
    std::cout << "Is Batch Ring Empty? " << (batchRing.isBufferEmpty() ? "YES" : "NO") << "\n";
    std::cout << "Is Batch Ring Full?  " << (batchRing.isBufferFull() ? "YES" : "NO") << "\n";
    batchRing.close();
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc33_circular_ring_buffer.cpp", tc33, expect_compile=True)
    results["tc33_circular_ring_buffer.cpp"] = (res, count, msg)

    # ── TC34: Disk File Cache Manager ─────────────────────────────────────────
    tc34 = r'''#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <chrono>
#include <iomanip>

struct CachePage {
    std::string pageId;
    std::vector<char> pageData;
    bool isDirty;
    long long lastAccessTimestamp;

    CachePage() : isDirty(false), lastAccessTimestamp(0) {}
    CachePage(std::string id, std::vector<char> data)
        : pageId(std::move(id)), pageData(std::move(data)), isDirty(false),
          lastAccessTimestamp(0) {}
};

class SimulatedDiskCacheManager {
private:
    size_t maxCachedPages;
    std::unordered_map<std::string, CachePage> cacheMap;
    size_t flushCount;
    size_t hitCount;
    size_t missCount;
    bool writeThroughMode;

public:
    explicit SimulatedDiskCacheManager(size_t maxPages = 4, bool writeThrough = false)
        : maxCachedPages(maxPages), flushCount(0), hitCount(0), missCount(0), writeThroughMode(writeThrough) {}

    void setWriteThroughMode(bool enable) {
        writeThroughMode = enable;
    }

    bool invalidate(const std::string& pageId) {
        auto it = cacheMap.find(pageId);
        if (it == cacheMap.end()) return false;
        if (it->second.isDirty) {
            std::cout << "  [FLUSH-ON-INVALIDATE] Flushing dirty page: " << pageId << "\n";
            flushCount++;
        }
        cacheMap.erase(it);
        return true;
    }

    double getHitRatio() const {
        size_t total = hitCount + missCount;
        return (total > 0) ? (static_cast<double>(hitCount) / total) : 0.0;
    }

    std::string readPage(const std::string& pageId) {
        auto it = cacheMap.find(pageId);
        if (it == cacheMap.end()) {
            missCount++;
            return "";
        }

        hitCount++;
        it->second.lastAccessTimestamp = getCurrentTimeMs();
        return std::string(it->second.pageData.begin(), it->second.pageData.end());
    }

    void writePage(const std::string& pageId, const std::string& content) {
        if (cacheMap.size() >= maxCachedPages && cacheMap.find(pageId) == cacheMap.end()) {
            evictOldestPage();
        }

        std::vector<char> bytes(content.begin(), content.end());
        CachePage page(pageId, bytes);
        page.isDirty = !writeThroughMode;
        page.lastAccessTimestamp = getCurrentTimeMs();
        cacheMap.insert_or_assign(pageId, page);

        if (writeThroughMode) {
            std::cout << "  [WRITE-THROUGH] Page directly committed to disk: " << pageId << "\n";
            flushCount++;
        }
    }

    void flushDirtyPages() {
        std::cout << "\n[FLUSH] Writing dirty pages to simulated storage:\n";
        for (auto& pair : cacheMap) {
            if (pair.second.isDirty) {
                std::cout << "  * Flushed page [" << pair.first << "] ("
                          << pair.second.pageData.size() << " bytes)\n";
                pair.second.isDirty = false;
                flushCount++;
            }
        }
    }

    void printCacheStatus() const {
        std::cout << "\n================ DISK CACHE STATUS ================\n";
        std::cout << "Active Pages: " << cacheMap.size() << " / " << maxCachedPages
                  << " | Total Flushes: " << flushCount << "\n";
        for (const auto& pair : cacheMap) {
            std::cout << "  Page [" << pair.first << "] Size: " << pair.second.pageData.size()
                      << " | Dirty: " << (pair.second.isDirty ? "YES" : "NO") << "\n";
        }
        std::cout << "===================================================\n";
    }

private:
    void evictOldestPage() {
        if (cacheMap.empty()) return;
        std::string oldestKey;
        long long oldestTime = -1;

        for (const auto& pair : cacheMap) {
            if (oldestTime == -1 || pair.second.lastAccessTimestamp < oldestTime) {
                oldestTime = pair.second.lastAccessTimestamp;
                oldestKey = pair.first;
            }
        }

        if (cacheMap[oldestKey].isDirty) {
            std::cout << "  [EVICT-FLUSH] Flushing dirty page before eviction: " << oldestKey << "\n";
            flushCount++;
        }
        cacheMap.erase(oldestKey);
    }

    static long long getCurrentTimeMs() {
        static long long counter = 1000;
        return ++counter;
    }
};

int main() {
    SimulatedDiskCacheManager cache(3);

    cache.writePage("page_001", "AST_DATA_SECTION_1");
    cache.writePage("page_002", "TYPE_ENV_DATA_SECTION_2");
    cache.writePage("page_003", "SYMBOL_TABLE_SECTION_3");
    cache.printCacheStatus();

    cache.readPage("page_001"); // Update timestamp of page 1

    std::cout << "\nWriting page_004 (should trigger eviction of page_002):\n";
    cache.writePage("page_004", "BYTECODE_PAYLOAD_SECTION_4");
    cache.printCacheStatus();

    cache.flushDirtyPages();
    cache.printCacheStatus();

    std::cout << "\nTesting Invalidation and Write-Through Mode:\n";
    cache.invalidate("page_001");
    cache.setWriteThroughMode(true);
    cache.writePage("page_005_critical", "PERSISTENT_RECOVERY_LOG");
    std::cout << "Cache Hit Ratio: " << std::fixed << std::setprecision(1) << (cache.getHitRatio() * 100.0) << "%\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc34_disk_file_cache_manager.cpp", tc34, expect_compile=True)
    results["tc34_disk_file_cache_manager.cpp"] = (res, count, msg)

    # ── TC35: Quadtree Spatial Index ──────────────────────────────────────────
    tc35 = r'''#include <iostream>
#include <vector>
#include <memory>
#include <cmath>
#include <iomanip>

struct SpatialPoint {
    double x, y;
    int id;

    SpatialPoint(double x_, double y_, int id_ = 0) : x(x_), y(y_), id(id_) {}
};

struct SpatialBoundingBox {
    double xMin, yMin, xMax, yMax;

    SpatialBoundingBox(double x0, double y0, double x1, double y1)
        : xMin(x0), yMin(y0), xMax(x1), yMax(y1) {}

    bool contains(const SpatialPoint& pt) const {
        return (pt.x >= xMin && pt.x <= xMax && pt.y >= yMin && pt.y <= yMax);
    }

    bool intersects(const SpatialBoundingBox& other) const {
        return !(other.xMin > xMax || other.xMax < xMin ||
                 other.yMin > yMax || other.yMax < yMin);
    }
};

class QuadtreeNode {
private:
    SpatialBoundingBox boundary;
    size_t capacity;
    std::vector<SpatialPoint> points;
    bool isDivided;

    std::unique_ptr<QuadtreeNode> northWest;
    std::unique_ptr<QuadtreeNode> northEast;
    std::unique_ptr<QuadtreeNode> southWest;
    std::unique_ptr<QuadtreeNode> southEast;

public:
    QuadtreeNode(SpatialBoundingBox b, size_t cap = 4)
        : boundary(b), capacity(cap), isDivided(false) {}

    bool insert(const SpatialPoint& pt) {
        if (!boundary.contains(pt)) return false;

        if (points.size() < capacity && !isDivided) {
            points.push_back(pt);
            return true;
        }

        if (!isDivided) {
            subdivide();
        }

        return (northWest->insert(pt) || northEast->insert(pt) ||
                southWest->insert(pt) || southEast->insert(pt));
    }

    void queryRange(const SpatialBoundingBox& range, std::vector<SpatialPoint>& found) const {
        if (!boundary.intersects(range)) return;

        for (const auto& p : points) {
            if (range.contains(p)) {
                found.push_back(p);
            }
        }

        if (isDivided) {
            northWest->queryRange(range, found);
            northEast->queryRange(range, found);
            southWest->queryRange(range, found);
            southEast->queryRange(range, found);
        }
    }

    size_t countPoints() const {
        size_t c = points.size();
        if (isDivided) {
            c += northWest->countPoints();
            c += northEast->countPoints();
            c += southWest->countPoints();
            c += southEast->countPoints();
        }
        return c;
    }

    void queryRadius(double cx, double cy, double radius, std::vector<SpatialPoint>& found) const {
        SpatialBoundingBox box(cx - radius, cy - radius, cx + radius, cy + radius);
        std::vector<SpatialPoint> candidates;
        queryRange(box, candidates);

        double rSquared = radius * radius;
        for (const auto& p : candidates) {
            double dx = p.x - cx;
            double dy = p.y - cy;
            if (dx * dx + dy * dy <= rSquared) {
                found.push_back(p);
            }
        }
    }

private:
    void subdivide() {
        double xMid = (boundary.xMin + boundary.xMax) / 2.0;
        double yMid = (boundary.yMin + boundary.yMax) / 2.0;

        northWest = std::make_unique<QuadtreeNode>(SpatialBoundingBox(boundary.xMin, yMid, xMid, boundary.yMax), capacity);
        northEast = std::make_unique<QuadtreeNode>(SpatialBoundingBox(xMid, yMid, boundary.xMax, boundary.yMax), capacity);
        southWest = std::make_unique<QuadtreeNode>(SpatialBoundingBox(boundary.xMin, boundary.yMin, xMid, yMid), capacity);
        southEast = std::make_unique<QuadtreeNode>(SpatialBoundingBox(xMid, boundary.yMin, boundary.xMax, yMid), capacity);

        isDivided = true;

        for (const auto& p : points) {
            northWest->insert(p) || northEast->insert(p) ||
            southWest->insert(p) || southEast->insert(p);
        }
        points.clear();
    }
};

int main() {
    QuadtreeNode root(SpatialBoundingBox(0.0, 0.0, 100.0, 100.0), 4);

    for (int i = 0; i < 25; ++i) {
        root.insert(SpatialPoint(i * 3.5, i * 3.8, i));
    }

    SpatialBoundingBox searchBox(20.0, 20.0, 60.0, 60.0);
    std::vector<SpatialPoint> results;
    root.queryRange(searchBox, results);

    std::cout << "Quadtree Spatial Range Search ([20, 20] -> [60, 60]):\n";
    std::cout << "Found " << results.size() << " points within range:\n";
    for (const auto& pt : results) {
        std::cout << "  Point #" << pt.id << " at (" << pt.x << ", " << pt.y << ")\n";
    }

    std::vector<SpatialPoint> circleResults;
    root.queryRadius(50.0, 50.0, 25.0, circleResults);
    std::cout << "\nRadius Search (Center: (50, 50), Radius: 25.0):\n";
    std::cout << "Found " << circleResults.size() << " points within circular radius.\n";
    for (const auto& cp : circleResults) {
        std::cout << "  * Circular Neighbor Point #" << cp.id << " at (" << cp.x << ", " << cp.y << ")\n";
    }
    std::cout << "Total Spatial Elements Indexed: " << root.countPoints() << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc35_quadtree_spatial_index.cpp", tc35, expect_compile=True)
    results["tc35_quadtree_spatial_index.cpp"] = (res, count, msg)

    # ── TC36: Regex NFA Evaluator ─────────────────────────────────────────────
    tc36 = r'''#include <iostream>
#include <string>
#include <vector>
#include <set>
#include <memory>
#include <stack>

struct NfaState {
    int id;
    char transitionChar; // '\0' for epsilon transition
    std::vector<std::shared_ptr<NfaState>> nextStates;
    bool isMatch;

    NfaState(int id_, char c = '\0')
        : id(id_), transitionChar(c), isMatch(false) {}
};

class NfaBuilder {
private:
    int stateCounter;

public:
    NfaBuilder() : stateCounter(0) {}

    std::shared_ptr<NfaState> createState(char c = '\0', bool isMatch = false) {
        auto s = std::make_shared<NfaState>(stateCounter++, c);
        s->isMatch = isMatch;
        return s;
    }

    // Build NFA for literal character
    std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> buildLiteral(char c) {
        auto in = createState('\0');
        auto trans = createState(c);
        auto out = createState('\0');
        in->nextStates.push_back(trans);
        trans->nextStates.push_back(out);
        return {in, out};
    }

    // Build Union (a | b)
    std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> buildUnion(
        std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> branchA,
        std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> branchB) {
        auto start = createState('\0');
        auto end = createState('\0');
        start->nextStates.push_back(branchA.first);
        start->nextStates.push_back(branchB.first);
        branchA.second->nextStates.push_back(end);
        branchB.second->nextStates.push_back(end);
        return {start, end};
    }

    // Build Kleene Star (a*)
    std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> buildStar(
        std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> body) {
        auto start = createState('\0');
        auto end = createState('\0');
        start->nextStates.push_back(body.first);
        start->nextStates.push_back(end);
        body.second->nextStates.push_back(body.first); // loopback
        body.second->nextStates.push_back(end);
        return {start, end};
    }
};

class SimpleNfaMatcher {
private:
    std::shared_ptr<NfaState> startState;

public:
    explicit SimpleNfaMatcher(std::shared_ptr<NfaState> start)
        : startState(std::move(start)) {}

    bool match(const std::string& input) const {
        std::set<std::shared_ptr<NfaState>> currentStates;
        addEpsilonStates(startState, currentStates);

        for (char c : input) {
            std::set<std::shared_ptr<NfaState>> nextStates;
            for (const auto& state : currentStates) {
                if (state->transitionChar == c) {
                    for (const auto& nxt : state->nextStates) {
                        addEpsilonStates(nxt, nextStates);
                    }
                }
            }
            currentStates = std::move(nextStates);
            if (currentStates.empty()) return false;
        }

        for (const auto& state : currentStates) {
            if (state->isMatch) return true;
        }
        return false;
    }

private:
    static void addEpsilonStates(const std::shared_ptr<NfaState>& state,
                                 std::set<std::shared_ptr<NfaState>>& stateSet) {
        if (!state || stateSet.find(state) != stateSet.end()) return;
        stateSet.insert(state);
        if (state->transitionChar == '\0') {
            for (const auto& nxt : state->nextStates) {
                addEpsilonStates(nxt, stateSet);
            }
        }
    }
};

int main() {
    // Construct NFA matching "a*b"
    auto s0 = std::make_shared<NfaState>(0, '\0');
    auto s1 = std::make_shared<NfaState>(1, 'a');
    auto s2 = std::make_shared<NfaState>(2, 'b');
    auto s3 = std::make_shared<NfaState>(3, '\0');
    s3->isMatch = true;

    s0->nextStates.push_back(s1);
    s0->nextStates.push_back(s2);
    s1->nextStates.push_back(s1); // Loop 'a*'
    s1->nextStates.push_back(s2);
    s2->nextStates.push_back(s3);

    SimpleNfaMatcher nfa(s0);

    std::vector<std::string> inputs = {"b", "ab", "aaaaab", "a", "ba", "aaba"};
    std::cout << "Testing NFA for pattern 'a*b':\n";
    for (const auto& inp : inputs) {
        std::cout << "  Input: '" << inp << "' -> " << (nfa.match(inp) ? "MATCH" : "REJECT") << "\n";
    }

    std::cout << "\nBuilding NFA for '(x | y)*z' using Thompson NfaBuilder:\n";
    NfaBuilder builder;
    auto litX = builder.buildLiteral('x');
    auto litY = builder.buildLiteral('y');
    auto unionXY = builder.buildUnion(litX, litY);
    auto starXY = builder.buildStar(unionXY);
    auto litZ = builder.buildLiteral('z');

    // Concat starXY and litZ
    starXY.second->nextStates.push_back(litZ.first);
    litZ.second->isMatch = true;

    SimpleNfaMatcher nfa2(starXY.first);
    std::vector<std::string> inputs2 = {"z", "xz", "yz", "xyxz", "yxyyz", "xy", "xyzq"};
    for (const auto& inp : inputs2) {
        std::cout << "  Input: '" << inp << "' -> " << (nfa2.match(inp) ? "MATCH" : "REJECT") << "\n";
    }

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc36_regex_nfa_evaluator.cpp", tc36, expect_compile=True)
    results["tc36_regex_nfa_evaluator.cpp"] = (res, count, msg)

    # ── TC37: Diagnostic Telemetry Collector ──────────────────────────────────
    tc37 = r'''#include <iostream>
#include <string>
#include <vector>
#include <numeric>
#include <algorithm>
#include <iomanip>
#include <cmath>

struct DiagnosticSample {
    std::string metricName;
    double value;
    std::string timestamp;

    DiagnosticSample(std::string name, double v, std::string ts)
        : metricName(std::move(name)), value(v), timestamp(std::move(ts)) {}
};

class TelemetryCollectorEngine {
private:
    std::vector<DiagnosticSample> samples;

public:
    void record(const std::string& metric, double val) {
        samples.emplace_back(metric, val, "2026-11-01 14:00:00");
    }

    std::vector<double> getValues(const std::string& metric) const {
        std::vector<double> vals;
        for (const auto& s : samples) {
            if (s.metricName == metric) vals.push_back(s.value);
        }
        std::sort(vals.begin(), vals.end());
        return vals;
    }

    double computePercentile(const std::string& metric, double p) const {
        auto vals = getValues(metric);
        if (vals.empty()) return 0.0;
        size_t idx = static_cast<size_t>(std::ceil(p * vals.size())) - 1;
        if (idx >= vals.size()) idx = vals.size() - 1;
        return vals[idx];
    }

    double computeMean(const std::string& metric) const {
        auto vals = getValues(metric);
        if (vals.empty()) return 0.0;
        double sum = std::accumulate(vals.begin(), vals.end(), 0.0);
        return sum / vals.size();
    }

    double computeStdDev(const std::string& metric) const {
        auto vals = getValues(metric);
        if (vals.size() < 2) return 0.0;
        double mean = computeMean(metric);
        double sqSum = 0.0;
        for (double v : vals) {
            double diff = v - mean;
            sqSum += diff * diff;
        }
        return std::sqrt(sqSum / (vals.size() - 1));
    }

    double computeMin(const std::string& metric) const {
        auto vals = getValues(metric);
        return vals.empty() ? 0.0 : vals.front();
    }

    double computeMax(const std::string& metric) const {
        auto vals = getValues(metric);
        return vals.empty() ? 0.0 : vals.back();
    }

    std::vector<DiagnosticSample> detectAnomalies(const std::string& metric, double sigmaThreshold = 3.0) const {
        std::vector<DiagnosticSample> anomalies;
        double mean = computeMean(metric);
        double stddev = computeStdDev(metric);
        if (stddev < 1e-6) return anomalies;

        for (const auto& s : samples) {
            if (s.metricName == metric && std::abs(s.value - mean) > (sigmaThreshold * stddev)) {
                anomalies.push_back(s);
            }
        }
        return anomalies;
    }

    std::vector<std::string> getDistinctMetricNames() const {
        std::vector<std::string> names;
        for (const auto& s : samples) {
            if (std::find(names.begin(), names.end(), s.metricName) == names.end()) {
                names.push_back(s.metricName);
            }
        }
        return names;
    }

    void clear() {
        samples.clear();
    }

    size_t totalSampleCount() const {
        return samples.size();
    }

    void printGlobalDashboard() const {
        std::cout << "\n================ GLOBAL TELEMETRY DASHBOARD ================\n";
        auto metrics = getDistinctMetricNames();
        std::cout << "Tracked Metrics: " << metrics.size() << " | Total Events: " << samples.size() << "\n";
        for (const auto& m : metrics) {
            std::cout << "  * [" << std::setw(22) << std::left << m << "] p50="
                      << std::setw(6) << computePercentile(m, 0.50)
                      << " | p95=" << std::setw(6) << computePercentile(m, 0.95)
                      << " | p99=" << std::setw(6) << computePercentile(m, 0.99) << "\n";
        }
        std::cout << "============================================================\n";
    }

    void printReport(const std::string& metric) const {
        auto vals = getValues(metric);
        if (vals.empty()) return;

        double sum = std::accumulate(vals.begin(), vals.end(), 0.0);
        double mean = sum / vals.size();

        std::cout << "\n================ METRIC: " << metric << " ================\n";
        std::cout << "Sample Count : " << vals.size() << "\n";
        std::cout << "Min / Max    : " << computeMin(metric) << " / " << computeMax(metric) << "\n";
        std::cout << "Mean Value   : " << std::fixed << std::setprecision(2) << mean << "\n";
        std::cout << "Std Dev      : " << computeStdDev(metric) << "\n";
        std::cout << "Percentile p50 (Median) : " << computePercentile(metric, 0.50) << "\n";
        std::cout << "Percentile p95          : " << computePercentile(metric, 0.95) << "\n";
        std::cout << "Percentile p99          : " << computePercentile(metric, 0.99) << "\n";

        auto anomalies = detectAnomalies(metric, 2.5);
        std::cout << "Detected Outlier Anomalies: " << anomalies.size() << "\n";
        for (const auto& a : anomalies) {
            std::cout << "  * Outlier at " << a.timestamp << " -> Value: " << a.value << "\n";
        }
        std::cout << "========================================================\n";
    }
};

int main() {
    TelemetryCollectorEngine telemetry;
    for (int i = 1; i <= 100; ++i) {
        telemetry.record("compiler_parse_ms", 10.0 + (i % 15) * 1.5 + (i > 95 ? 120.0 : 0.0));
        telemetry.record("memory_rss_mb", 120.0 + (i * 0.8));
    }

    telemetry.printReport("compiler_parse_ms");
    telemetry.printReport("memory_rss_mb");
    telemetry.printGlobalDashboard();
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc37_diagnostic_telemetry_collector.cpp", tc37, expect_compile=True)
    results["tc37_diagnostic_telemetry_collector.cpp"] = (res, count, msg)

    # ── TC38: Bloom Filter Hash Family ────────────────────────────────────────
    tc38 = r'''#include <iostream>
#include <string>
#include <vector>
#include <cmath>
#include <iomanip>
#include <cstdint>

class BloomFilterEngine {
private:
    std::vector<bool> bitset;
    size_t filterSize;
    size_t hashFunctionCount;

    size_t hash1(const std::string& s) const {
        size_t h = 5381;
        for (char c : s) h = ((h << 5) + h) + static_cast<unsigned char>(c);
        return h % filterSize;
    }

    size_t hash2(const std::string& s) const {
        size_t h = 0;
        for (char c : s) h = static_cast<unsigned char>(c) + (h << 6) + (h << 16) - h;
        return h % filterSize;
    }

    static uint32_t murmurMix32(uint32_t h) {
        h ^= h >> 16;
        h *= 0x85ebca6b;
        h ^= h >> 13;
        h *= 0xc2b2ae35;
        h ^= h >> 16;
        return h;
    }

    size_t hash3(const std::string& s) const {
        uint32_t h = 0x9747b28c;
        for (char c : s) {
            h ^= static_cast<uint8_t>(c);
            h = murmurMix32(h);
        }
        return h % filterSize;
    }

    size_t getHash(const std::string& s, size_t i) const {
        return (hash1(s) + i * hash2(s) + i * i * hash3(s)) % filterSize;
    }

public:
    BloomFilterEngine(size_t sizeBits, size_t kHashes)
        : bitset(sizeBits, false), filterSize(sizeBits), hashFunctionCount(kHashes) {}

    void insert(const std::string& key) {
        for (size_t i = 0; i < hashFunctionCount; ++i) {
            bitset[getHash(key, i)] = true;
        }
    }

    bool contains(const std::string& key) const {
        for (size_t i = 0; i < hashFunctionCount; ++i) {
            if (!bitset[getHash(key, i)]) return false;
        }
        return true;
    }

    static size_t calculateOptimalSize(size_t expectedItems, double targetFpr) {
        double m = -(expectedItems * std::log(targetFpr)) / (0.480453); // (ln 2)^2
        return static_cast<size_t>(std::ceil(m));
    }

    static size_t calculateOptimalHashes(size_t sizeBits, size_t expectedItems) {
        double k = (static_cast<double>(sizeBits) / expectedItems) * 0.693147; // ln 2
        return std::max<size_t>(1, static_cast<size_t>(std::round(k)));
    }

    size_t countSetBits() const {
        size_t count = 0;
        for (bool b : bitset) {
            if (b) count++;
        }
        return count;
    }

    double getFillRatio() const {
        return static_cast<double>(countSetBits()) / filterSize;
    }

    void clear() {
        std::fill(bitset.begin(), bitset.end(), false);
    }

    double estimateFalsePositiveRate(size_t numInserted) const {
        double m = static_cast<double>(filterSize);
        double k = static_cast<double>(hashFunctionCount);
        double n = static_cast<double>(numInserted);
        return std::pow(1.0 - std::exp(-k * n / m), k);
    }
};

int main() {
    BloomFilterEngine filter(512, 4);

    std::vector<std::string> keywords = {"struct", "class", "template", "typename", "constexpr", "inline"};
    for (const auto& kw : keywords) filter.insert(kw);

    std::cout << "Testing Bloom Filter Keyword Queries:\n";
    for (const auto& kw : keywords) {
        std::cout << "  Query '" << kw << "': " << (filter.contains(kw) ? "PRESENT" : "MISSING") << "\n";
    }

    std::cout << "  Query 'definitely_not_a_keyword': "
              << (filter.contains("definitely_not_a_keyword") ? "FALSE_POSITIVE" : "ABSENT") << "\n";

    std::cout << "Estimated False Positive Rate: " << std::fixed << std::setprecision(4)
              << filter.estimateFalsePositiveRate(keywords.size()) << "\n";
    std::cout << "Filter Fill Ratio: " << (filter.getFillRatio() * 100.0) << "%\n";

    std::cout << "\nDesigning Optimal Bloom Filter for 100,000 items with FPR = 0.01 (1%):\n";
    size_t optBits = BloomFilterEngine::calculateOptimalSize(100000, 0.01);
    size_t optHashes = BloomFilterEngine::calculateOptimalHashes(optBits, 100000);
    std::cout << "  Required Bits  : " << optBits << " bits (" << (optBits / 8192) << " KB)\n";
    std::cout << "  Required Hashes: " << optHashes << " hash functions\n";

    BloomFilterEngine largeFilter(optBits, optHashes);
    for (int i = 0; i < 1000; ++i) {
        largeFilter.insert("token_id_" + std::to_string(i * 17));
    }
    std::cout << "Inserted 1000 items. Query membership:\n";
    std::cout << "  Query 'token_id_34': " << (largeFilter.contains("token_id_34") ? "FOUND" : "NOT_FOUND") << "\n";
    std::cout << "  Query 'token_id_999999': " << (largeFilter.contains("token_id_999999") ? "FALSE_ALARM" : "CLEAN_MISS") << "\n";

    std::cout << "\nCounting Set Bits in Large Filter:\n";
    std::cout << "  Total Bits Set : " << largeFilter.countSetBits() << "\n";
    std::cout << "  Fill Percentage: " << std::fixed << std::setprecision(2)
              << (largeFilter.getFillRatio() * 100.0) << "%\n";

    largeFilter.clear();
    std::cout << "After clear, set bits: " << largeFilter.countSetBits() << "\n";
    std::cout << "Is empty after clear? " << (largeFilter.countSetBits() == 0 ? "YES" : "NO") << "\n";
    std::cout << "Filter Total Capacity: " << optBits << " bits (" << (optBits / 8) << " bytes)\n";

    // Stress query batch
    int falsePosCount = 0;
    for (int q = 10000; q < 10100; ++q) {
        if (filter.contains("unseen_key_" + std::to_string(q))) falsePosCount++;
    }
    std::cout << "False alarms across 100 unseen probes: " << falsePosCount << "\n";
    std::cout << "Bloom filter verification completed.\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc38_bloom_filter_hash_family.cpp", tc38, expect_compile=True)
    results["tc38_bloom_filter_hash_family.cpp"] = (res, count, msg)

    # ── TC39: Dependency Injector Container ───────────────────────────────────
    tc39 = r'''#include <iostream>
#include <string>
#include <memory>
#include <unordered_map>
#include <typeindex>
#include <functional>

class ILoggerService {
public:
    virtual ~ILoggerService() = default;
    virtual void log(const std::string& msg) = 0;
};

class ConsoleLoggerService : public ILoggerService {
public:
    void log(const std::string& msg) override {
        std::cout << "[IOC-CONSOLE] " << msg << "\n";
    }
};

class IFileSystemService {
public:
    virtual ~IFileSystemService() = default;
    virtual bool exists(const std::string& path) = 0;
    virtual std::string readFile(const std::string& path) = 0;
};

class MockFileSystemService : public IFileSystemService {
public:
    bool exists(const std::string& path) override { return !path.empty(); }
    std::string readFile(const std::string& path) override {
        return "// Simulated source code payload from " + path;
    }
};

class ISecurityPolicyService {
public:
    virtual ~ISecurityPolicyService() = default;
    virtual bool validateToken(const std::string& token) = 0;
};

class EnterpriseSecurityPolicyService : public ISecurityPolicyService {
public:
    bool validateToken(const std::string& token) override {
        return token == "TOKEN_VALID_2026";
    }
};

class ICompilerPipeline {
public:
    virtual ~ICompilerPipeline() = default;
    virtual void compile(const std::string& sourceFile) = 0;
};

class StandardCompilerPipeline : public ICompilerPipeline {
private:
    std::shared_ptr<ILoggerService> logger;
    std::shared_ptr<IFileSystemService> fs;
    std::shared_ptr<ISecurityPolicyService> security;

public:
    StandardCompilerPipeline(std::shared_ptr<ILoggerService> l,
                             std::shared_ptr<IFileSystemService> f,
                             std::shared_ptr<ISecurityPolicyService> s)
        : logger(std::move(l)), fs(std::move(f)), security(std::move(s)) {}

    void compile(const std::string& sourceFile) override {
        logger->log("Verifying security policy for compile request...");
        if (!security->validateToken("TOKEN_VALID_2026")) {
            logger->log("ERROR: Security policy rejected compile request.");
            return;
        }

        logger->log("Reading file from filesystem: " + sourceFile);
        std::string src = fs->readFile(sourceFile);
        logger->log("Compiling AST. Total bytes: " + std::to_string(src.size()));
        logger->log("Compilation succeeded cleanly.");
    }
};

class DependencyInjectionContainer {
private:
    std::unordered_map<std::type_index, std::shared_ptr<void>> singletons;
    std::unordered_map<std::type_index, std::function<std::shared_ptr<void>()>> transientFactories;

public:
    template <typename Interface, typename Implementation>
    void registerSingleton() {
        singletons[std::type_index(typeid(Interface))] = std::make_shared<Implementation>();
    }

    template <typename Interface, typename Implementation>
    void registerTransient() {
        transientFactories[std::type_index(typeid(Interface))] = []() -> std::shared_ptr<void> {
            return std::make_shared<Implementation>();
        };
    }

    template <typename Interface>
    std::shared_ptr<Interface> resolve() {
        auto it = singletons.find(std::type_index(typeid(Interface)));
        if (it != singletons.end()) {
            return std::static_pointer_cast<Interface>(it->second);
        }
        auto tIt = transientFactories.find(std::type_index(typeid(Interface)));
        if (tIt != transientFactories.end()) {
            return std::static_pointer_cast<Interface>(tIt->second());
        }
        return nullptr;
    }

    DependencyInjectionContainer createChildScope() const {
        DependencyInjectionContainer child;
        child.singletons = this->singletons;
        child.transientFactories = this->transientFactories;
        return child;
    }

    size_t getRegisteredSingletonCount() const { return singletons.size(); }
    size_t getRegisteredTransientCount() const { return transientFactories.size(); }
};

int main() {
    DependencyInjectionContainer ioc;
    ioc.registerSingleton<ILoggerService, ConsoleLoggerService>();
    ioc.registerSingleton<IFileSystemService, MockFileSystemService>();
    ioc.registerSingleton<ISecurityPolicyService, EnterpriseSecurityPolicyService>();

    auto logger = ioc.resolve<ILoggerService>();
    auto fs = ioc.resolve<IFileSystemService>();
    auto security = ioc.resolve<ISecurityPolicyService>();

    StandardCompilerPipeline pipeline(logger, fs, security);
    pipeline.compile("main.cpp");

    std::cout << "\nResolving Transient Instances:\n";
    ioc.registerTransient<ILoggerService, ConsoleLoggerService>();
    auto loggerA = ioc.resolve<ILoggerService>();
    auto loggerB = ioc.resolve<ILoggerService>();
    std::cout << "Are transient instances distinct pointers? " << (loggerA != loggerB ? "YES" : "NO") << "\n";

    std::cout << "\nInspecting Child Scope Container:\n";
    auto childScope = ioc.createChildScope();
    std::cout << "Child Singletons Count: " << childScope.getRegisteredSingletonCount() << "\n";
    auto childLogger = childScope.resolve<ILoggerService>();
    if (childLogger) childLogger->log("Child scope resolved logger successfully.");

    auto childSecurity = childScope.resolve<ISecurityPolicyService>();
    std::cout << "Child Token Validation: "
              << (childSecurity && childSecurity->validateToken("TOKEN_VALID_2026") ? "PASSED" : "FAILED") << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc39_dependency_injector_container.cpp", tc39, expect_compile=True)
    results["tc39_dependency_injector_container.cpp"] = (res, count, msg)

    # ── TC40: Task Scheduler Cron Sim ─────────────────────────────────────────
    tc40 = r'''#include <iostream>
#include <string>
#include <vector>
#include <functional>
#include <chrono>
#include <iomanip>

enum class JobRunStatus { SCHEDULED, ACTIVE, PAUSED, COMPLETED, FAILED };

struct ScheduledJob {
    std::string jobName;
    int intervalSeconds;
    int executionCount;
    int maxRuns; // 0 for infinite
    JobRunStatus status;
    std::function<void()> taskCallback;

    ScheduledJob(std::string name, int interval, std::function<void()> cb, int maxR = 0)
        : jobName(std::move(name)), intervalSeconds(interval),
          executionCount(0), maxRuns(maxR), status(JobRunStatus::SCHEDULED),
          taskCallback(std::move(cb)) {}
};

class SimulatedCronScheduler {
private:
    std::vector<ScheduledJob> jobs;
    int simulatedClockSeconds;
    int totalDispatches;

public:
    SimulatedCronScheduler() : simulatedClockSeconds(0), totalDispatches(0) {}

    void registerJob(std::string name, int interval, std::function<void()> cb, int maxRuns = 0) {
        jobs.emplace_back(std::move(name), interval, std::move(cb), maxRuns);
    }

    bool pauseJob(const std::string& name) {
        for (auto& job : jobs) {
            if (job.jobName == name) {
                job.status = JobRunStatus::PAUSED;
                return true;
            }
        }
        return false;
    }

    bool resumeJob(const std::string& name) {
        for (auto& job : jobs) {
            if (job.jobName == name && job.status == JobRunStatus::PAUSED) {
                job.status = JobRunStatus::SCHEDULED;
                return true;
            }
        }
        return false;
    }

    bool cancelJob(const std::string& name) {
        for (auto it = jobs.begin(); it != jobs.end(); ++it) {
            if (it->jobName == name) {
                jobs.erase(it);
                return true;
            }
        }
        return false;
    }

    size_t getJobCount() const { return jobs.size(); }
    int getClock() const { return simulatedClockSeconds; }

    void advanceTime(int seconds) {
        for (int t = 1; t <= seconds; ++t) {
            simulatedClockSeconds++;
            for (auto& job : jobs) {
                if (job.status == JobRunStatus::PAUSED || job.status == JobRunStatus::COMPLETED) {
                    continue;
                }

                if (simulatedClockSeconds % job.intervalSeconds == 0) {
                    job.executionCount++;
                    totalDispatches++;
                    std::cout << "[CRON t=" << simulatedClockSeconds << "s] Triggered: " << job.jobName << "\n";
                    if (job.taskCallback) {
                        try {
                            job.taskCallback();
                        } catch (const std::exception& e) {
                            std::cerr << "  ERROR in job '" << job.jobName << "': " << e.what() << "\n";
                            job.status = JobRunStatus::FAILED;
                        }
                    }
                    if (job.maxRuns > 0 && job.executionCount >= job.maxRuns) {
                        job.status = JobRunStatus::COMPLETED;
                        std::cout << "  -> Job '" << job.jobName << "' completed all " << job.maxRuns << " runs.\n";
                    }
                }
            }
        }
    }

    void printSummary() const {
        std::cout << "\n================ CRON SCHEDULER SUMMARY ================\n";
        std::cout << "Simulated Clock   : " << simulatedClockSeconds << " seconds\n";
        std::cout << "Total Dispatches  : " << totalDispatches << "\n";
        for (const auto& job : jobs) {
            std::cout << "  Job: " << std::setw(20) << std::left << job.jobName
                      << " | Interval: " << std::setw(3) << job.intervalSeconds << "s"
                      << " | Runs: " << std::setw(3) << job.executionCount
                      << " | Status: " << statusToString(job.status) << "\n";
        }
        std::cout << "========================================================\n";
    }

private:
    static const char* statusToString(JobRunStatus s) {
        switch (s) {
            case JobRunStatus::SCHEDULED: return "SCHEDULED";
            case JobRunStatus::ACTIVE:    return "ACTIVE";
            case JobRunStatus::PAUSED:    return "PAUSED";
            case JobRunStatus::COMPLETED: return "COMPLETED";
            case JobRunStatus::FAILED:    return "FAILED";
            default: return "UNKNOWN";
        }
    }
};

int main() {
    SimulatedCronScheduler cron;
    cron.registerJob("CacheFlush", 5, []() { std::cout << "    -> Purged expired AST cache.\n"; });
    cron.registerJob("HeartbeatCheck", 10, []() { std::cout << "    -> Health check status: OK.\n"; });
    cron.registerJob("DailyBackup", 30, []() { std::cout << "    -> Incremental snapshot saved.\n"; });
    cron.registerJob("OneShotBootstrap", 2, []() { std::cout << "    -> System boot initialization executed.\n"; }, 1);

    std::cout << "Advancing Cron Scheduler by 15 seconds:\n";
    cron.advanceTime(15);
    cron.printSummary();

    std::cout << "\nPausing 'CacheFlush' and advancing 15 more seconds:\n";
    cron.pauseJob("CacheFlush");
    cron.advanceTime(15);
    cron.printSummary();

    std::cout << "\nCancelling 'HeartbeatCheck' and Resuming 'CacheFlush':\n";
    cron.cancelJob("HeartbeatCheck");
    cron.resumeJob("CacheFlush");
    cron.advanceTime(10);
    cron.printSummary();

    std::cout << "Scheduler Simulation Concluded. Final Clock: " << cron.getClock() << "s\n";
    std::cout << "Total Scheduled Jobs Active: " << cron.getJobCount() << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc40_task_scheduler_cron_sim.cpp", tc40, expect_compile=True)
    results["tc40_task_scheduler_cron_sim.cpp"] = (res, count, msg)

    return results
