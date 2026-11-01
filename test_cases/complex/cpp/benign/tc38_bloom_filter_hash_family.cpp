#include <iostream>
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
