#include <iostream>
#include <vector>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <future>
#include <atomic>
#include <chrono>

class ThreadPoolWorkerEngine {
private:
    std::vector<std::thread> workerThreads;
    std::queue<std::function<void()>> taskQueue;
    std::mutex queueMutex;
    std::condition_variable cvTaskReady;
    std::condition_variable cvAllDone;
    std::atomic<bool> isStopped;
    std::atomic<size_t> completedTasks;
    std::atomic<size_t> activeWorkerCount;

public:
    explicit ThreadPoolWorkerEngine(size_t threadCount = 4)
        : isStopped(false), completedTasks(0), activeWorkerCount(0) {
        for (size_t i = 0; i < threadCount; ++i) {
            workerThreads.emplace_back([this, i]() {
                this->workerLoop(i);
            });
        }
    }

    ~ThreadPoolWorkerEngine() {
        shutdown();
    }

    template <typename F, typename... Args>
    auto enqueueTask(F&& f, Args&&... args) 
        -> std::future<typename std::invoke_result<F, Args...>::type> {
        using ReturnType = typename std::invoke_result<F, Args...>::type;

        auto taskPtr = std::make_shared<std::packaged_task<ReturnType()>>(
            std::bind(std::forward<F>(f), std::forward<Args>(args)...)
        );

        std::future<ReturnType> taskFuture = taskPtr->get_future();
        {
            std::unique_lock<std::mutex> lock(queueMutex);
            if (isStopped) {
                throw std::runtime_error("Cannot enqueue task into stopped thread pool");
            }
            taskQueue.emplace([taskPtr]() {
                (*taskPtr)();
            });
        }
        cvTaskReady.notify_one();
        return taskFuture;
    }

    void waitForAllTasks() {
        std::unique_lock<std::mutex> lock(queueMutex);
        cvAllDone.wait(lock, [this]() {
            return taskQueue.empty() && (activeWorkerCount == 0);
        });
    }

    void shutdown() {
        {
            std::unique_lock<std::mutex> lock(queueMutex);
            if (isStopped) return;
            isStopped = true;
        }
        cvTaskReady.notify_all();
        for (auto& th : workerThreads) {
            if (th.joinable()) {
                th.join();
            }
        }
    }

    size_t getCompletedCount() const { return completedTasks.load(); }
    size_t getPendingCount() {
        std::unique_lock<std::mutex> lock(queueMutex);
        return taskQueue.size();
    }

private:
    void workerLoop(size_t workerId) {
        while (true) {
            std::function<void()> currentTask;
            {
                std::unique_lock<std::mutex> lock(queueMutex);
                cvTaskReady.wait(lock, [this]() {
                    return isStopped || !taskQueue.empty();
                });

                if (isStopped && taskQueue.empty()) {
                    return;
                }

                currentTask = std::move(taskQueue.front());
                taskQueue.pop();
                activeWorkerCount++;
            }

            try {
                currentTask();
                completedTasks++;
            } catch (const std::exception& e) {
                std::cerr << "Worker #" << workerId << " caught exception: " << e.what() << "\n";
            }

            {
                std::unique_lock<std::mutex> lock(queueMutex);
                activeWorkerCount--;
                if (taskQueue.empty() && activeWorkerCount == 0) {
                    cvAllDone.notify_all();
                }
            }
        }
    }
};

long long computeFactorial(int n) {
    long long res = 1;
    for (int i = 2; i <= n; ++i) res = (res * i) % 1000000007;
    return res;
}

std::vector<int> generateFibonacciSeries(int count) {
    std::vector<int> fibs;
    if (count <= 0) return fibs;
    fibs.push_back(0);
    if (count == 1) return fibs;
    fibs.push_back(1);
    for (int i = 2; i < count; ++i) {
        fibs.push_back(fibs[i - 1] + fibs[i - 2]);
    }
    return fibs;
}

int main() {
    ThreadPoolWorkerEngine pool(4);
    std::vector<std::future<long long>> futures;
    std::vector<std::future<std::vector<int>>> fibFutures;

    for (int i = 10; i <= 25; ++i) {
        futures.push_back(pool.enqueueTask(computeFactorial, i));
    }

    for (int count : {10, 15, 20, 25}) {
        fibFutures.push_back(pool.enqueueTask(generateFibonacciSeries, count));
    }

    std::cout << "Submitted 16 factorial tasks and 4 Fibonacci tasks to thread pool.\n";
    pool.waitForAllTasks();

    for (size_t i = 0; i < futures.size(); ++i) {
        long long val = futures[i].get();
        std::cout << "Factorial Task #" << i << " result = " << val << "\n";
    }

    for (size_t i = 0; i < fibFutures.size(); ++i) {
        auto series = fibFutures[i].get();
        std::cout << "Fibonacci Task #" << i << " count = " << series.size()
                  << ", last element = " << (series.empty() ? 0 : series.back()) << "\n";
    }

    std::cout << "Total completed tasks in pool: " << pool.getCompletedCount() << "\n";
    return 0;
}
