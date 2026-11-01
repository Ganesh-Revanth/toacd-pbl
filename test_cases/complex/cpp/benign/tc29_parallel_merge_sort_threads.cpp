#include <iostream>
#include <vector>
#include <thread>
#include <algorithm>
#include <chrono>

void merge(std::vector<int>& arr, int left, int mid, int right) {
    std::vector<int> temp(right - left + 1);
    int i = left, j = mid + 1, k = 0;

    while (i <= mid && j <= right) {
        temp[k++] = (arr[i] <= arr[j]) ? arr[i++] : arr[j++];
    }
    while (i <= mid) temp[k++] = arr[i++];
    while (j <= right) temp[k++] = arr[j++];

    for (int p = 0; p < k; ++p) {
        arr[left + p] = temp[p];
    }
}

void sequentialMergeSort(std::vector<int>& arr, int left, int right) {
    if (left >= right) return;
    int mid = left + (right - left) / 2;
    sequentialMergeSort(arr, left, mid);
    sequentialMergeSort(arr, mid + 1, right);
    merge(arr, left, mid, right);
}

template <typename T>
class ParallelSorterEngine {
public:
    static void sort(std::vector<T>& data, int maxThreads = 4) {
        if (data.size() <= 1) return;
        parallelSortInternal(data, 0, static_cast<int>(data.size() - 1), 0, maxThreads);
    }

    static void parallelQuickSort(std::vector<T>& data, int maxThreads = 4) {
        if (data.size() <= 1) return;
        quickSortInternal(data, 0, static_cast<int>(data.size() - 1), 0, maxThreads);
    }

private:
    static int partition(std::vector<T>& arr, int low, int high) {
        T pivot = arr[high];
        int i = low - 1;
        for (int j = low; j < high; ++j) {
            if (arr[j] <= pivot) {
                i++;
                std::swap(arr[i], arr[j]);
            }
        }
        std::swap(arr[i + 1], arr[high]);
        return i + 1;
    }

    static void quickSortInternal(std::vector<T>& arr, int low, int high, int depth, int maxThreads) {
        if (low < high) {
            int pi = partition(arr, low, high);
            if ((1 << depth) < maxThreads) {
                std::thread t1(quickSortInternal, std::ref(arr), low, pi - 1, depth + 1, maxThreads);
                std::thread t2(quickSortInternal, std::ref(arr), pi + 1, high, depth + 1, maxThreads);
                t1.join();
                t2.join();
            } else {
                quickSortInternal(arr, low, pi - 1, depth + 1, maxThreads);
                quickSortInternal(arr, pi + 1, high, depth + 1, maxThreads);
            }
        }
    }

    static void mergeInternal(std::vector<T>& arr, int left, int mid, int right) {
        std::vector<T> temp;
        temp.reserve(right - left + 1);
        int i = left, j = mid + 1;

        while (i <= mid && j <= right) {
            if (arr[i] <= arr[j]) temp.push_back(arr[i++]);
            else temp.push_back(arr[j++]);
        }
        while (i <= mid) temp.push_back(arr[i++]);
        while (j <= right) temp.push_back(arr[j++]);

        for (size_t p = 0; p < temp.size(); ++p) {
            arr[left + p] = std::move(temp[p]);
        }
    }

    static void parallelSortInternal(std::vector<T>& arr, int left, int right, int depth, int maxThreads) {
        if (left >= right) return;
        int mid = left + (right - left) / 2;

        if ((1 << depth) < maxThreads) {
            std::thread t1(parallelSortInternal, std::ref(arr), left, mid, depth + 1, maxThreads);
            std::thread t2(parallelSortInternal, std::ref(arr), mid + 1, right, depth + 1, maxThreads);
            t1.join();
            t2.join();
        } else {
            parallelSortInternal(arr, left, mid, depth + 1, maxThreads);
            parallelSortInternal(arr, mid + 1, right, depth + 1, maxThreads);
        }
        mergeInternal(arr, left, mid, right);
    }
};

int main() {
    std::vector<int> numbers = {64, 34, 25, 12, 22, 11, 90, 88, 76, 54, 43, 32, 21, 10, 5, 1};
    std::cout << "Original Array: ";
    for (int n : numbers) std::cout << n << " ";
    std::cout << "\n";

    auto t0 = std::chrono::high_resolution_clock::now();
    ParallelSorterEngine<int>::sort(numbers, 4);
    auto t1 = std::chrono::high_resolution_clock::now();

    std::cout << "Sorted Array  : ";
    for (int n : numbers) std::cout << n << " ";
    std::cout << "\n";

    bool sorted = std::is_sorted(numbers.begin(), numbers.end());
    std::cout << "Sorted Check  : " << (sorted ? "PASSED" : "FAILED") << "\n";

    auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count();
    std::cout << "Sort completed in " << elapsed << " microseconds.\n";

    std::vector<std::string> stringList = {"zeta", "alpha", "gamma", "beta", "theta", "delta", "epsilon"};
    std::cout << "\nSorting String Vector via Generic ParallelSorter:\n";
    ParallelSorterEngine<std::string>::sort(stringList, 2);
    for (const auto& s : stringList) std::cout << s << " ";
    std::cout << "\n";

    std::vector<int> quickNumbers = {99, 44, 22, 88, 11, 77, 33, 66, 55, 0};
    std::cout << "\nSorting via Parallel QuickSort:\n";
    ParallelSorterEngine<int>::parallelQuickSort(quickNumbers, 4);
    for (int n : quickNumbers) std::cout << n << " ";
    std::cout << "\nQuickSort Check: " << (std::is_sorted(quickNumbers.begin(), quickNumbers.end()) ? "PASSED" : "FAILED") << "\n";

    std::vector<double> doubleNumbers = {3.14, 1.41, 2.718, 0.577, 1.618, 0.0, -1.0};
    std::cout << "\nSorting Double Precision Floats:\n";
    ParallelSorterEngine<double>::sort(doubleNumbers, 2);
    for (double d : doubleNumbers) std::cout << d << " ";
    std::cout << "\nFloat Sort Check: " << (std::is_sorted(doubleNumbers.begin(), doubleNumbers.end()) ? "PASSED" : "FAILED") << "\n";

    std::vector<int> largeArray(500);
    for (int i = 0; i < 500; ++i) largeArray[i] = (500 - i);
    ParallelSorterEngine<int>::sort(largeArray, 4);
    std::cout << "500-element reverse-sorted array verified: "
              << (std::is_sorted(largeArray.begin(), largeArray.end()) ? "YES" : "NO") << "\n";

    return 0;
}
