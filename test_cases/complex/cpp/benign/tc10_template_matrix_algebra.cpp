#include <iostream>
#include <vector>
#include <iomanip>
#include <stdexcept>
#include <cmath>

template <typename T, size_t Rows, size_t Cols>
class MatrixAlgebra {
private:
    std::vector<std::vector<T>> data;

public:
    MatrixAlgebra() : data(Rows, std::vector<T>(Cols, T{})) {}

    explicit MatrixAlgebra(const std::vector<std::vector<T>>& init) : data(init) {
        if (init.size() != Rows || (Rows > 0 && init[0].size() != Cols)) {
            throw std::invalid_argument("Initializer dimensions do not match Matrix parameters");
        }
    }

    T& at(size_t r, size_t c) {
        if (r >= Rows || c >= Cols) throw std::out_of_range("Matrix index out of bounds");
        return data[r][c];
    }

    const T& at(size_t r, size_t c) const {
        if (r >= Rows || c >= Cols) throw std::out_of_range("Matrix index out of bounds");
        return data[r][c];
    }

    MatrixAlgebra<T, Rows, Cols> operator+(const MatrixAlgebra<T, Rows, Cols>& rhs) const {
        MatrixAlgebra<T, Rows, Cols> res;
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                res.at(r, c) = data[r][c] + rhs.at(r, c);
            }
        }
        return res;
    }

    template <size_t OtherCols>
    MatrixAlgebra<T, Rows, OtherCols> operator*(const MatrixAlgebra<T, Cols, OtherCols>& rhs) const {
        MatrixAlgebra<T, Rows, OtherCols> res;
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t oc = 0; oc < OtherCols; ++oc) {
                T sum = T{};
                for (size_t k = 0; k < Cols; ++k) {
                    sum += data[r][k] * rhs.at(k, oc);
                }
                res.at(r, oc) = sum;
            }
        }
        return res;
    }

    MatrixAlgebra<T, Rows, Cols> operator*(T scalar) const {
        MatrixAlgebra<T, Rows, Cols> res;
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                res.at(r, c) = data[r][c] * scalar;
            }
        }
        return res;
    }

    bool operator==(const MatrixAlgebra<T, Rows, Cols>& rhs) const {
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                if (std::abs(data[r][c] - rhs.at(r, c)) > 1e-7) return false;
            }
        }
        return true;
    }

    T computeTrace() const {
        static_assert(Rows == Cols, "Trace is only defined for square matrices");
        T traceSum = T{};
        for (size_t i = 0; i < Rows; ++i) {
            traceSum += data[i][i];
        }
        return traceSum;
    }

    static MatrixAlgebra<T, Rows, Cols> identity() {
        static_assert(Rows == Cols, "Identity matrix must be square");
        MatrixAlgebra<T, Rows, Cols> id;
        for (size_t i = 0; i < Rows; ++i) {
            id.at(i, i) = static_cast<T>(1);
        }
        return id;
    }

    MatrixAlgebra<T, Cols, Rows> transpose() const {
        MatrixAlgebra<T, Cols, Rows> res;
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                res.at(c, r) = data[r][c];
            }
        }
        return res;
    }

    void print(const std::string& label = "") const {
        if (!label.empty()) std::cout << "--- " << label << " ---\n";
        for (size_t r = 0; r < Rows; ++r) {
            std::cout << "[ ";
            for (size_t c = 0; c < Cols; ++c) {
                std::cout << std::setw(8) << std::fixed << std::setprecision(2) << data[r][c] << " ";
            }
            std::cout << "]\n";
        }
    }
};

double compute3x3Determinant(const MatrixAlgebra<double, 3, 3>& m) {
    double a = m.at(0, 0), b = m.at(0, 1), c = m.at(0, 2);
    double d = m.at(1, 0), e = m.at(1, 1), f = m.at(1, 2);
    double g = m.at(2, 0), h = m.at(2, 1), i = m.at(2, 2);
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
}

int main() {
    MatrixAlgebra<double, 3, 3> matA({
        {1.0, 2.0, 3.0},
        {0.0, 1.0, 4.0},
        {5.0, 6.0, 0.0}
    });

    MatrixAlgebra<double, 3, 3> matB({
        {2.0, 0.0, -1.0},
        {1.0, 3.0,  2.0},
        {0.0, -2.0, 1.0}
    });

    matA.print("Matrix A");
    matB.print("Matrix B");

    auto matSum = matA + matB;
    matSum.print("A + B");

    auto matProd = matA * matB;
    matProd.print("A * B");

    double det = compute3x3Determinant(matA);
    std::cout << "Determinant of Matrix A: " << det << "\n";

    auto scaled = matA * 2.5;
    scaled.print("Matrix A scaled by 2.5");

    auto id = MatrixAlgebra<double, 3, 3>::identity();
    id.print("3x3 Identity Matrix");

    std::cout << "Trace of Matrix A: " << matA.computeTrace() << "\n";
    std::cout << "Trace of Identity: " << id.computeTrace() << "\n";

    auto trans = matA.transpose();
    trans.print("Matrix A Transposed");
    std::cout << "Is (A^T)^T equal to A? " << ((trans.transpose() == matA) ? "YES" : "NO") << "\n";

    return 0;
}
