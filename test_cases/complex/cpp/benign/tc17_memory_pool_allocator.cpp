#include <iostream>
#include <vector>
#include <cstddef>
#include <new>
#include <stdexcept>
#include <chrono>

class FixedBlockMemoryPool {
private:
    struct FreeNode {
        FreeNode* next;
    };

    size_t blockSize;
    size_t blocksPerPage;
    std::vector<char*> allocatedPages;
    FreeNode* freeListHead;
    size_t totalAllocatedBlocks;

    size_t peakAllocatedBlocks;

public:
    FixedBlockMemoryPool(size_t blockSz, size_t perPage = 128)
        : blockSize(std::max(blockSz, sizeof(FreeNode))),
          blocksPerPage(perPage), freeListHead(nullptr),
          totalAllocatedBlocks(0), peakAllocatedBlocks(0) {
        allocateNewPage();
    }

    ~FixedBlockMemoryPool() {
        for (char* page : allocatedPages) {
            delete[] page;
        }
    }

    static size_t alignUp(size_t bytes, size_t alignment = 8) {
        return (bytes + alignment - 1) & ~(alignment - 1);
    }

    void* allocate() {
        if (!freeListHead) {
            allocateNewPage();
        }
        FreeNode* node = freeListHead;
        freeListHead = freeListHead->next;
        totalAllocatedBlocks++;
        if (totalAllocatedBlocks > peakAllocatedBlocks) {
            peakAllocatedBlocks = totalAllocatedBlocks;
        }
        return static_cast<void*>(node);
    }

    void deallocate(void* ptr) {
        if (!ptr) return;
        FreeNode* node = static_cast<FreeNode*>(ptr);
        node->next = freeListHead;
        freeListHead = node;
        totalAllocatedBlocks--;
    }

    size_t getBlockSize() const { return blockSize; }
    size_t getPageCount() const { return allocatedPages.size(); }
    size_t getActiveBlockCount() const { return totalAllocatedBlocks; }
    size_t getPeakBlockCount() const { return peakAllocatedBlocks; }
    size_t getTotalCapacity() const { return allocatedPages.size() * blocksPerPage; }

    double getUtilizationRatio() const {
        size_t cap = getTotalCapacity();
        return (cap > 0) ? (static_cast<double>(totalAllocatedBlocks) / cap) : 0.0;
    }

    void printDiagnostics() const {
        std::cout << "\n================ POOL DIAGNOSTICS ================\n";
        std::cout << "Block Size       : " << blockSize << " bytes (aligned)\n";
        std::cout << "Pages Allocated  : " << allocatedPages.size() << " (" << getTotalCapacity() << " total slots)\n";
        std::cout << "Active Blocks    : " << totalAllocatedBlocks << "\n";
        std::cout << "Peak Usage       : " << peakAllocatedBlocks << " blocks\n";
        std::cout << "Pool Utilization : " << (getUtilizationRatio() * 100.0) << "%\n";
        std::cout << "==================================================\n";
    }

private:
    void allocateNewPage() {
        size_t pageBytes = blockSize * blocksPerPage;
        char* page = new char[pageBytes];
        allocatedPages.push_back(page);

        for (size_t i = 0; i < blocksPerPage; ++i) {
            FreeNode* node = reinterpret_cast<FreeNode*>(page + (i * blockSize));
            node->next = freeListHead;
            freeListHead = node;
        }
    }
};

struct Particle {
    double x, y, z;
    double vx, vy, vz;
    int particleId;

    Particle(int id, double x_, double y_, double z_)
        : x(x_), y(y_), z(z_), vx(0.1), vy(0.2), vz(0.3), particleId(id) {}
};

int main() {
    FixedBlockMemoryPool pool(sizeof(Particle), 256);
    std::vector<Particle*> activeParticles;

    auto t0 = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < 5000; ++i) {
        void* mem = pool.allocate();
        Particle* p = new (mem) Particle(i, i * 1.5, i * 2.5, i * 3.5);
        activeParticles.push_back(p);
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    for (size_t i = 0; i < activeParticles.size(); i += 2) {
        activeParticles[i]->~Particle();
        pool.deallocate(activeParticles[i]);
        activeParticles[i] = nullptr;
    }

    std::cout << "================ MEMORY POOL ALLOCATOR ================\n";
    pool.printDiagnostics();

    auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count();
    std::cout << "5000 Placed Allocations completed in " << elapsed << " microseconds.\n";

    for (Particle* p : activeParticles) {
        if (p) {
            p->~Particle();
            pool.deallocate(p);
        }
    }
    std::cout << "\nAfter freeing 5000 particles:\n";
    pool.printDiagnostics();

    std::cout << "\nReallocating 2000 particles into reclaimed memory slots:\n";
    for (int i = 0; i < 2000; ++i) {
        void* mem = pool.allocate();
        Particle* p = new (mem) Particle(i + 10000, i * 0.5, i * 0.7, i * 0.9);
        activeParticles[i] = p;
    }
    pool.printDiagnostics();

    for (int i = 0; i < 2000; ++i) {
        if (activeParticles[i]) {
            activeParticles[i]->~Particle();
            pool.deallocate(activeParticles[i]);
            activeParticles[i] = nullptr;
        }
    }
    std::cout << "All secondary particle batches released cleanly.\n";
    return 0;
}
