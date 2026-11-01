#include <iostream>
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
