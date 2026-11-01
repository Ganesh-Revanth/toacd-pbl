#include <iostream>
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
