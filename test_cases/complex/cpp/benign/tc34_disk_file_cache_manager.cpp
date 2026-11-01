#include <iostream>
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
