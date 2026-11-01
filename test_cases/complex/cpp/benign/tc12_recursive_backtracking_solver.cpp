#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <iomanip>

class NQueensSolver {
private:
    int boardSize;
    std::vector<int> queenPositions; // queenPositions[row] = col
    std::vector<std::vector<int>> allSolutions;

    bool isSafe(int row, int col) const {
        for (int prevRow = 0; prevRow < row; ++prevRow) {
            int prevCol = queenPositions[prevRow];
            if (prevCol == col) return false; // same column
            if (std::abs(prevRow - row) == std::abs(prevCol - col)) return false; // diagonal
        }
        return true;
    }

    void solveRecursive(int currentRow) {
        if (currentRow == boardSize) {
            allSolutions.push_back(queenPositions);
            return;
        }

        for (int col = 0; col < boardSize; ++col) {
            if (isSafe(currentRow, col)) {
                queenPositions[currentRow] = col;
                solveRecursive(currentRow + 1);
            }
        }
    }

public:
    explicit NQueensSolver(int n) : boardSize(n), queenPositions(n, -1) {}

    void executeSolve() {
        allSolutions.clear();
        solveRecursive(0);
    }

    size_t getSolutionCount() const { return allSolutions.size(); }

    void printFirstSolution() const {
        if (allSolutions.empty()) {
            std::cout << "No solutions exist for N = " << boardSize << "\n";
            return;
        }

        std::cout << "\nFirst Solution for N = " << boardSize << " Queens:\n";
        const auto& sol = allSolutions[0];
        for (int r = 0; r < boardSize; ++r) {
            std::cout << "  ";
            for (int c = 0; c < boardSize; ++c) {
                std::cout << (sol[r] == c ? "[Q]" : " . ");
            }
            std::cout << "\n";
        }
    }
};

class SudokuBacktrackingEngine {
private:
    std::vector<std::vector<int>> grid;

    bool isValid(int r, int c, int val) const {
        for (int i = 0; i < 9; ++i) {
            if (grid[r][i] == val) return false;
            if (grid[i][c] == val) return false;
        }
        int startR = (r / 3) * 3;
        int startC = (c / 3) * 3;
        for (int dr = 0; dr < 3; ++dr) {
            for (int dc = 0; dc < 3; ++dc) {
                if (grid[startR + dr][startC + dc] == val) return false;
            }
        }
        return true;
    }

public:
    explicit SudokuBacktrackingEngine(std::vector<std::vector<int>> g) : grid(std::move(g)) {}

    bool solve() {
        for (int r = 0; r < 9; ++r) {
            for (int c = 0; c < 9; ++c) {
                if (grid[r][c] == 0) {
                    for (int val = 1; val <= 9; ++val) {
                        if (isValid(r, c, val)) {
                            grid[r][c] = val;
                            if (solve()) return true;
                            grid[r][c] = 0; // backtrack
                        }
                    }
                    return false;
                }
            }
        }
        return true;
    }

    bool isBoardValid() {
        for (int r = 0; r < 9; ++r) {
            for (int c = 0; c < 9; ++c) {
                if (grid[r][c] != 0) {
                    int val = grid[r][c];
                    grid[r][c] = 0;
                    bool ok = isValid(r, c, val);
                    grid[r][c] = val;
                    if (!ok) return false;
                }
            }
        }
        return true;
    }

    int countEmptyCells() const {
        int emptyCount = 0;
        for (int r = 0; r < 9; ++r) {
            for (int c = 0; c < 9; ++c) {
                if (grid[r][c] == 0) emptyCount++;
            }
        }
        return emptyCount;
    }

    void printGrid() const {
        std::cout << "-------------------------\n";
        for (int r = 0; r < 9; ++r) {
            std::cout << "| ";
            for (int c = 0; c < 9; ++c) {
                std::cout << grid[r][c] << " ";
                if ((c + 1) % 3 == 0) std::cout << "| ";
            }
            std::cout << "\n";
            if ((r + 1) % 3 == 0) std::cout << "-------------------------\n";
        }
    }
};

int main() {
    std::cout << "================ RECURSIVE BACKTRACKING ================\n";
    for (int n = 4; n <= 8; ++n) {
        NQueensSolver solver(n);
        solver.executeSolve();
        std::cout << "N = " << n << " Queens Solutions Count: " << solver.getSolutionCount() << "\n";
        if (n == 4 || n == 8) solver.printFirstSolution();
    }

    std::vector<std::vector<int>> sudokuBoard = {
        {5, 3, 0, 0, 7, 0, 0, 0, 0},
        {6, 0, 0, 1, 9, 5, 0, 0, 0},
        {0, 9, 8, 0, 0, 0, 0, 6, 0},
        {8, 0, 0, 0, 6, 0, 0, 0, 3},
        {4, 0, 0, 8, 0, 3, 0, 0, 1},
        {7, 0, 0, 0, 2, 0, 0, 0, 6},
        {0, 6, 0, 0, 0, 0, 2, 8, 0},
        {0, 0, 0, 4, 1, 9, 0, 0, 5},
        {0, 0, 0, 0, 8, 0, 0, 7, 9}
    };

    std::cout << "\nSolving 9x9 Sudoku via Backtracking:\n";
    SudokuBacktrackingEngine sudoku(sudokuBoard);
    std::cout << "Initial Board Validity: " << (sudoku.isBoardValid() ? "VALID" : "INVALID") << "\n";
    std::cout << "Empty Cells to Solve  : " << sudoku.countEmptyCells() << "\n";
    if (sudoku.solve()) {
        std::cout << "Solved Board State:\n";
        sudoku.printGrid();
    } else {
        std::cout << "No valid Sudoku solution found.\n";
    }
    return 0;
}
