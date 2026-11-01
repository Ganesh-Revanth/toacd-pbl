"""
scripts/generate_complex/cpp_benign_part2.py
--------------------------------------------
Generates C++ benign complex fixtures 11 through 20.
Each fixture: 150-500 lines, compiles cleanly with g++ -std=c++17.
"""

from pathlib import Path
from typing import Dict, Tuple
from .utils import validate_and_write


def generate_all(base_dir: Path) -> Dict[str, Tuple[bool, int, str]]:
    results = {}

    # ── TC11: CSV File Stream Processor ───────────────────────────────────────
    tc11 = r'''#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <fstream>
#include <map>
#include <iomanip>
#include <cmath>
#include <stdexcept>
#include <algorithm>

struct DataField {
    std::string stringVal;
    double numericVal;
    bool isNumeric;

    DataField() : numericVal(0.0), isNumeric(false) {}
    explicit DataField(std::string str) : stringVal(std::move(str)), numericVal(0.0), isNumeric(false) {
        try {
            size_t idx = 0;
            numericVal = std::stod(stringVal, &idx);
            if (idx == stringVal.size()) isNumeric = true;
        } catch (...) {
            isNumeric = false;
        }
    }
};

class CsvRecordRow {
private:
    std::vector<DataField> fields;

public:
    void addField(const std::string& raw) {
        fields.emplace_back(raw);
    }

    size_t size() const { return fields.size(); }
    const DataField& get(size_t index) const {
        if (index >= fields.size()) throw std::out_of_range("CSV column index out of range");
        return fields[index];
    }
};

class CsvDataTable {
private:
    std::vector<std::string> headers;
    std::vector<CsvRecordRow> rows;

public:
    void setHeaders(const std::vector<std::string>& hdrs) {
        headers = hdrs;
    }

    void addRow(const CsvRecordRow& row) {
        rows.push_back(row);
    }

    size_t getRowCount() const { return rows.size(); }
    size_t getColumnCount() const { return headers.size(); }

    int findColumnIndex(const std::string& name) const {
        for (size_t i = 0; i < headers.size(); ++i) {
            if (headers[i] == name) return static_cast<int>(i);
        }
        return -1;
    }

    double computeColumnMean(const std::string& colName) const {
        int idx = findColumnIndex(colName);
        if (idx == -1) throw std::invalid_argument("Column not found: " + colName);

        double sum = 0.0;
        size_t count = 0;
        for (const auto& row : rows) {
            if (static_cast<size_t>(idx) < row.size() && row.get(idx).isNumeric) {
                sum += row.get(idx).numericVal;
                count++;
            }
        }
        return (count > 0) ? (sum / count) : 0.0;
    }

    double computeColumnStdDev(const std::string& colName) const {
        double mean = computeColumnMean(colName);
        int idx = findColumnIndex(colName);
        double varianceSum = 0.0;
        size_t count = 0;

        for (const auto& row : rows) {
            if (static_cast<size_t>(idx) < row.size() && row.get(idx).isNumeric) {
                double diff = row.get(idx).numericVal - mean;
                varianceSum += diff * diff;
                count++;
            }
        }
        return (count > 1) ? std::sqrt(varianceSum / (count - 1)) : 0.0;
    }

    void printTableSummary() const {
        std::cout << "\n================ CSV DATA SUMMARY ================\n";
        std::cout << "Dimensions: " << rows.size() << " rows x " << headers.size() << " columns\n";
        std::cout << "Headers   : ";
        for (const auto& h : headers) std::cout << "[" << h << "] ";
        std::cout << "\n--------------------------------------------------\n";
        for (const auto& h : headers) {
            int idx = findColumnIndex(h);
            if (idx != -1 && rows.size() > 0 && rows[0].get(idx).isNumeric) {
                std::cout << "  Column '" << std::setw(15) << std::left << h << "' -> Mean: "
                          << std::setw(8) << std::fixed << std::setprecision(2) << computeColumnMean(h)
                          << " | StdDev: " << computeColumnStdDev(h) << "\n";
            }
        }
        std::cout << "==================================================\n";
    }
};

class CsvStreamParserEngine {
public:
    static CsvDataTable parseFromString(const std::string& csvData) {
        CsvDataTable table;
        std::istringstream stream(csvData);
        std::string line;

        bool headerParsed = false;
        while (std::getline(stream, line)) {
            if (line.empty() || line[0] == '#') continue;

            std::vector<std::string> tokens = tokenizeLine(line);
            if (!headerParsed) {
                table.setHeaders(tokens);
                headerParsed = true;
            } else {
                CsvRecordRow row;
                for (const auto& tok : tokens) row.addField(tok);
                table.addRow(row);
            }
        }
        return table;
    }

private:
    static std::vector<std::string> tokenizeLine(const std::string& line) {
        std::vector<std::string> tokens;
        std::string cur;
        bool inQuotes = false;

        for (size_t i = 0; i < line.size(); ++i) {
            char c = line[i];
            if (c == '"') {
                inQuotes = !inQuotes;
            } else if (c == ',' && !inQuotes) {
                tokens.push_back(trim(cur));
                cur.clear();
            } else {
                cur += c;
            }
        }
        tokens.push_back(trim(cur));
        return tokens;
    }

    static std::string trim(const std::string& s) {
        size_t start = s.find_first_not_of(" \t\r\n");
        if (start == std::string::npos) return "";
        size_t end = s.find_last_not_of(" \t\r\n");
        return s.substr(start, end - start + 1);
    }
};

int main() {
    std::string mockCsv = 
        "Timestamp,Module,LatencyMs,MemoryMB,ThroughputRps\n"
        "2026-11-01T10:00,Parser,12.4,128.5,1450.0\n"
        "2026-11-01T10:01,Lexer,8.2,95.0,2100.0\n"
        "2026-11-01T10:02,TypeCheck,24.6,210.2,850.0\n"
        "2026-11-01T10:03,Optimizer,45.8,320.0,420.0\n"
        "2026-11-01T10:04,CodeGen,18.5,165.4,1150.0\n"
        "2026-11-01T10:05,Healer,15.1,142.0,1320.0\n";

    CsvDataTable dataset = CsvStreamParserEngine::parseFromString(mockCsv);
    dataset.printTableSummary();
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc11_csv_file_stream_processor.cpp", tc11, expect_compile=True)
    results["tc11_csv_file_stream_processor.cpp"] = (res, count, msg)

    # ── TC12: Recursive Backtracking Solver ───────────────────────────────────
    tc12 = r'''#include <iostream>
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
'''
    res, count, msg = validate_and_write(base_dir / "tc12_recursive_backtracking_solver.cpp", tc12, expect_compile=True)
    results["tc12_recursive_backtracking_solver.cpp"] = (res, count, msg)

    # ── TC13: LRU Cache Template STL ──────────────────────────────────────────
    tc13 = r'''#include <iostream>
#include <string>
#include <list>
#include <vector>
#include <unordered_map>
#include <optional>
#include <stdexcept>
#include <iomanip>
#include <chrono>

template <typename Key, typename Value>
class GenericLruCache {
public:
    using KeyValuePair = std::pair<Key, Value>;
    using ListIterator = typename std::list<KeyValuePair>::iterator;

private:
    size_t capacity;
    std::list<KeyValuePair> itemsList;
    std::unordered_map<Key, ListIterator> lookupTable;
    size_t hitCount;
    size_t missCount;

public:
    explicit GenericLruCache(size_t cap)
        : capacity(cap), hitCount(0), missCount(0) {
        if (capacity == 0) throw std::invalid_argument("Capacity must be positive");
    }

    void put(const Key& key, const Value& val) {
        auto it = lookupTable.find(key);
        if (it != lookupTable.end()) {
            itemsList.erase(it->second);
            lookupTable.erase(it);
        } else if (lookupTable.size() >= capacity) {
            auto oldest = itemsList.back();
            lookupTable.erase(oldest.first);
            itemsList.pop_back();
        }

        itemsList.emplace_front(key, val);
        lookupTable[key] = itemsList.begin();
    }

    std::optional<Value> get(const Key& key) {
        auto it = lookupTable.find(key);
        if (it == lookupTable.end()) {
            missCount++;
            return std::nullopt;
        }

        hitCount++;
        Value foundVal = it->second->second;
        itemsList.erase(it->second);
        itemsList.emplace_front(key, foundVal);
        lookupTable[key] = itemsList.begin();
        return foundVal;
    }

    std::optional<Value> peek(const Key& key) const {
        auto it = lookupTable.find(key);
        if (it == lookupTable.end()) return std::nullopt;
        return it->second->second;
    }

    bool remove(const Key& key) {
        auto it = lookupTable.find(key);
        if (it == lookupTable.end()) return false;
        itemsList.erase(it->second);
        lookupTable.erase(it);
        return true;
    }

    void clear() {
        itemsList.clear();
        lookupTable.clear();
        hitCount = 0;
        missCount = 0;
    }

    std::vector<Key> getKeys() const {
        std::vector<Key> keys;
        for (const auto& pair : itemsList) {
            keys.push_back(pair.first);
        }
        return keys;
    }

    bool contains(const Key& key) const {
        return lookupTable.find(key) != lookupTable.end();
    }

    size_t size() const { return lookupTable.size(); }
    size_t getCapacity() const { return capacity; }
    size_t getHits() const { return hitCount; }
    size_t getMisses() const { return missCount; }

    double getHitRatio() const {
        size_t total = hitCount + missCount;
        return (total > 0) ? (static_cast<double>(hitCount) / total) : 0.0;
    }

    void printState() const {
        std::cout << "\n================ LRU CACHE STATE ================\n";
        std::cout << "Capacity : " << capacity << " | Current Size: " << lookupTable.size() << "\n";
        std::cout << "Hits     : " << hitCount << " | Misses: " << missCount
                  << " | Hit Ratio: " << std::fixed << std::setprecision(1) << (getHitRatio() * 100.0) << "%\n";
        std::cout << "MRU -> LRU Chain:\n";
        for (const auto& pair : itemsList) {
            std::cout << "  [" << pair.first << " : " << pair.second << "]\n";
        }
        std::cout << "=================================================\n";
    }
};

int main() {
    GenericLruCache<std::string, int> cache(4);

    cache.put("kernel_ast", 101);
    cache.put("type_env", 202);
    cache.put("symbol_table", 303);
    cache.put("cfg_graph", 404);

    cache.printState();

    auto val1 = cache.get("kernel_ast"); // Hit, brings kernel_ast to front
    std::cout << "Access 'kernel_ast': " << (val1.has_value() ? std::to_string(val1.value()) : "MISS") << "\n";

    cache.put("bytecode_bin", 505); // Evicts type_env (oldest)
    cache.printState();

    auto val2 = cache.get("type_env"); // Miss
    std::cout << "Access 'type_env': " << (val2.has_value() ? std::to_string(val2.value()) : "MISS") << "\n";

    cache.put("ssa_ir", 606); // Evicts symbol_table
    cache.printState();

    std::cout << "\nPeek 'ssa_ir' without reordering: ";
    auto peekVal = cache.peek("ssa_ir");
    std::cout << (peekVal.has_value() ? std::to_string(peekVal.value()) : "MISS") << "\n";

    std::cout << "Removing 'cfg_graph': " << (cache.remove("cfg_graph") ? "SUCCESS" : "NOT_FOUND") << "\n";
    cache.printState();

    auto activeKeys = cache.getKeys();
    std::cout << "Active Cache Keys: ";
    for (const auto& k : activeKeys) std::cout << "[" << k << "] ";
    std::cout << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc13_lru_cache_template_stl.cpp", tc13, expect_compile=True)
    results["tc13_lru_cache_template_stl.cpp"] = (res, count, msg)

    # ── TC14: Command History Undo/Redo ────────────────────────────────────────
    tc14 = r'''#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <algorithm>

class TextDocument {
private:
    std::string content;

public:
    TextDocument() = default;

    void insert(size_t pos, const std::string& text) {
        if (pos > content.size()) pos = content.size();
        content.insert(pos, text);
    }

    void erase(size_t pos, size_t length) {
        if (pos >= content.size()) return;
        content.erase(pos, length);
    }

    const std::string& getContent() const { return content; }
};

class IDocumentCommand {
public:
    virtual ~IDocumentCommand() = default;
    virtual void execute(TextDocument& doc) = 0;
    virtual void undo(TextDocument& doc) = 0;
    virtual std::string describe() const = 0;
};

class InsertTextCommand : public IDocumentCommand {
private:
    size_t insertPosition;
    std::string textToInsert;

public:
    InsertTextCommand(size_t pos, std::string text)
        : insertPosition(pos), textToInsert(std::move(text)) {}

    void execute(TextDocument& doc) override {
        doc.insert(insertPosition, textToInsert);
    }

    void undo(TextDocument& doc) override {
        doc.erase(insertPosition, textToInsert.size());
    }

    std::string describe() const override {
        return "Insert '" + textToInsert + "' at " + std::to_string(insertPosition);
    }
};

class DeleteTextCommand : public IDocumentCommand {
private:
    size_t deletePosition;
    size_t deleteLength;
    std::string deletedSnapshot;

public:
    DeleteTextCommand(size_t pos, size_t len)
        : deletePosition(pos), deleteLength(len) {}

    void execute(TextDocument& doc) override {
        const std::string& c = doc.getContent();
        if (deletePosition < c.size()) {
            deletedSnapshot = c.substr(deletePosition, deleteLength);
            doc.erase(deletePosition, deleteLength);
        }
    }

    void undo(TextDocument& doc) override {
        doc.insert(deletePosition, deletedSnapshot);
    }

    std::string describe() const override {
        return "Delete len " + std::to_string(deleteLength) + " at " + std::to_string(deletePosition);
    }
};

class CommandHistoryManager {
private:
    TextDocument document;
    std::vector<std::unique_ptr<IDocumentCommand>> undoStack;
    std::vector<std::unique_ptr<IDocumentCommand>> redoStack;
    size_t maxHistorySize;

public:
    explicit CommandHistoryManager(size_t maxSize = 50) : maxHistorySize(maxSize) {}

    void executeCommand(std::unique_ptr<IDocumentCommand> cmd) {
        if (!cmd) return;
        cmd->execute(document);
        undoStack.push_back(std::move(cmd));
        redoStack.clear();

        if (undoStack.size() > maxHistorySize) {
            undoStack.erase(undoStack.begin());
        }
    }

    bool undo() {
        if (undoStack.empty()) return false;
        auto cmd = std::move(undoStack.back());
        undoStack.pop_back();
        cmd->undo(document);
        redoStack.push_back(std::move(cmd));
        return true;
    }

    bool redo() {
        if (redoStack.empty()) return false;
        auto cmd = std::move(redoStack.back());
        redoStack.pop_back();
        cmd->execute(document);
        undoStack.push_back(std::move(cmd));
        return true;
    }

    const std::string& getCurrentText() const {
        return document.getContent();
    }

    void printHistory() const {
        std::cout << "\nDocument Content: \"" << document.getContent() << "\"\n";
        std::cout << "Undo Stack (" << undoStack.size() << "):\n";
        for (const auto& cmd : undoStack) {
            std::cout << "  <- [UNDO] " << cmd->describe() << "\n";
        }
        std::cout << "Redo Stack (" << redoStack.size() << "):\n";
        for (const auto& cmd : redoStack) {
            std::cout << "  -> [REDO] " << cmd->describe() << "\n";
        }
    }
};

int main() {
    CommandHistoryManager editor;

    editor.executeCommand(std::make_unique<InsertTextCommand>(0, "Hello World"));
    editor.executeCommand(std::make_unique<InsertTextCommand>(11, " in C++17"));
    editor.executeCommand(std::make_unique<DeleteTextCommand>(0, 6)); // deletes "Hello "

    editor.printHistory();

    std::cout << "\nPerforming Undo Operation...\n";
    editor.undo();
    editor.printHistory();

    std::cout << "\nPerforming Another Undo Operation...\n";
    editor.undo();
    editor.printHistory();

    std::cout << "\nPerforming Redo Operation...\n";
    editor.redo();
    editor.printHistory();

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc14_command_history_undo_redo.cpp", tc14, expect_compile=True)
    results["tc14_command_history_undo_redo.cpp"] = (res, count, msg)

    # ── TC15: Priority Event Queue ────────────────────────────────────────────
    tc15 = r'''#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <iomanip>
#include <chrono>

struct ScheduledTaskEvent {
    int taskId;
    int priority; // lower value = higher urgency
    long long scheduledTimestampMs;
    std::string taskName;

    ScheduledTaskEvent() : taskId(0), priority(100), scheduledTimestampMs(0) {}
    ScheduledTaskEvent(int id, int prio, long long ts, std::string name)
        : taskId(id), priority(prio), scheduledTimestampMs(ts), taskName(std::move(name)) {}

    bool isHigherPriorityThan(const ScheduledTaskEvent& other) const {
        if (priority != other.priority) return priority < other.priority;
        return scheduledTimestampMs < other.scheduledTimestampMs;
    }
};

class BinaryMinHeapQueue {
private:
    std::vector<ScheduledTaskEvent> heap;

    size_t parent(size_t i) const { return (i - 1) / 2; }
    size_t leftChild(size_t i) const { return 2 * i + 1; }
    size_t rightChild(size_t i) const { return 2 * i + 2; }

    void siftUp(size_t i) {
        while (i > 0 && heap[i].isHigherPriorityThan(heap[parent(i)])) {
            std::swap(heap[i], heap[parent(i)]);
            i = parent(i);
        }
    }

    void siftDown(size_t i) {
        size_t minIndex = i;
        size_t l = leftChild(i);
        size_t r = rightChild(i);

        if (l < heap.size() && heap[l].isHigherPriorityThan(heap[minIndex])) {
            minIndex = l;
        }
        if (r < heap.size() && heap[r].isHigherPriorityThan(heap[minIndex])) {
            minIndex = r;
        }

        if (i != minIndex) {
            std::swap(heap[i], heap[minIndex]);
            siftDown(minIndex);
        }
    }

public:
    void push(const ScheduledTaskEvent& event) {
        heap.push_back(event);
        siftUp(heap.size() - 1);
    }

    ScheduledTaskEvent pop() {
        if (heap.empty()) throw std::underflow_error("Priority queue is empty");
        ScheduledTaskEvent top = heap.front();
        heap.front() = heap.back();
        heap.pop_back();
        if (!heap.empty()) siftDown(0);
        return top;
    }

    const ScheduledTaskEvent& peek() const {
        if (heap.empty()) throw std::underflow_error("Priority queue is empty");
        return heap.front();
    }

    bool cancelTask(int taskId) {
        for (size_t i = 0; i < heap.size(); ++i) {
            if (heap[i].taskId == taskId) {
                heap[i] = heap.back();
                heap.pop_back();
                if (i < heap.size()) {
                    siftDown(i);
                    siftUp(i);
                }
                return true;
            }
        }
        return false;
    }

    bool updatePriority(int taskId, int newPriority) {
        for (size_t i = 0; i < heap.size(); ++i) {
            if (heap[i].taskId == taskId) {
                int oldPrio = heap[i].priority;
                heap[i].priority = newPriority;
                if (newPriority < oldPrio) {
                    siftUp(i);
                } else {
                    siftDown(i);
                }
                return true;
            }
        }
        return false;
    }

    std::vector<ScheduledTaskEvent> drainAll() {
        std::vector<ScheduledTaskEvent> drained;
        while (!heap.empty()) {
            drained.push_back(pop());
        }
        return drained;
    }

    bool empty() const { return heap.empty(); }
    size_t size() const { return heap.size(); }

    void dumpHeapOrder() const {
        std::cout << "\n================ MIN-HEAP PRIORITY QUEUE ================\n";
        std::cout << "Total Queued Tasks: " << heap.size() << "\n";
        for (size_t i = 0; i < heap.size(); ++i) {
            std::cout << "  [" << std::setw(2) << i << "] Priority: " << std::setw(3) << heap[i].priority
                      << " | ID: " << std::setw(4) << heap[i].taskId
                      << " | Name: " << heap[i].taskName << "\n";
        }
        std::cout << "=========================================================\n";
    }
};

int main() {
    BinaryMinHeapQueue taskQueue;

    taskQueue.push(ScheduledTaskEvent(101, 5, 1000, "Background Log Flush"));
    taskQueue.push(ScheduledTaskEvent(102, 1, 1050, "Security Patch Validation"));
    taskQueue.push(ScheduledTaskEvent(103, 3, 1100, "AST Garbage Collection"));
    taskQueue.push(ScheduledTaskEvent(104, 1, 1020, "Compiler Error Auto-Heal"));
    taskQueue.push(ScheduledTaskEvent(105, 10, 1200, "Daily Telemetry Export"));
    taskQueue.push(ScheduledTaskEvent(106, 2, 1010, "High-Priority Sandbox Audit"));

    taskQueue.dumpHeapOrder();

    std::cout << "\nUpdating Task 105 Priority from 10 to 0 (Critical Emergency):\n";
    taskQueue.updatePriority(105, 0);
    taskQueue.dumpHeapOrder();

    std::cout << "\nCancelling Task 103 (AST Garbage Collection): "
              << (taskQueue.cancelTask(103) ? "CANCELLED" : "NOT_FOUND") << "\n";
    taskQueue.dumpHeapOrder();

    std::cout << "\nProcessing tasks by strict priority dispatch:\n";
    while (!taskQueue.empty()) {
        auto top = taskQueue.pop();
        std::cout << "  -> Dispatched Task [" << top.taskId << "] '" << top.taskName
                  << "' (Priority " << top.priority << ")\n";
    }

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc15_priority_event_queue.cpp", tc15, expect_compile=True)
    results["tc15_priority_event_queue.cpp"] = (res, count, msg)

    # ── TC16: Config Env Parser (Tests FPR) ────────────────────────────────────
    tc16 = r'''#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <sstream>
#include <cstdlib>
#include <iomanip>
#include <stdexcept>

class SystemConfigEnvParser {
private:
    std::map<std::string, std::map<std::string, std::string>> sections;
    std::string systemHostHome;
    std::string systemUserProfile;
    std::string authBypassSecretToken;
    bool enableAdminBypass;

public:
    SystemConfigEnvParser() : enableAdminBypass(false) {
        // Legitimate environment variable lookups for local filesystem paths
        const char* home = std::getenv("HOME");
        systemHostHome = home ? std::string(home) : "/var/default_home";

        const char* prof = std::getenv("USERPROFILE");
        systemUserProfile = prof ? std::string(prof) : "C:\\Users\\Default";

        authBypassSecretToken = "LOCAL-DEV-TOKEN-99";
    }

    void setAdminBypassAllowed(bool allowed) {
        enableAdminBypass = allowed;
    }

    void loadFromIniString(const std::string& iniContent) {
        std::istringstream stream(iniContent);
        std::string line;
        std::string currentSection = "global";

        while (std::getline(stream, line)) {
            // Trim whitespace
            size_t start = line.find_first_not_of(" \t\r\n");
            if (start == std::string::npos || line[start] == '#' || line[start] == ';') continue;
            size_t end = line.find_last_not_of(" \t\r\n");
            line = line.substr(start, end - start + 1);

            if (line.front() == '[' && line.back() == ']') {
                currentSection = line.substr(1, line.size() - 2);
            } else {
                size_t eq = line.find('=');
                if (eq != std::string::npos) {
                    std::string key = line.substr(0, eq);
                    std::string val = line.substr(eq + 1);
                    // Trim key and val
                    key = key.substr(0, key.find_last_not_of(" \t") + 1);
                    val = val.substr(val.find_first_not_of(" \t"));
                    sections[currentSection][key] = val;
                }
            }
        }
    }

    std::string getString(const std::string& sec, const std::string& key, const std::string& fallback = "") const {
        auto sIt = sections.find(sec);
        if (sIt != sections.end()) {
            auto kIt = sIt->second.find(key);
            if (kIt != sIt->second.end()) return kIt->second;
        }
        return fallback;
    }

    int getInt(const std::string& sec, const std::string& key, int fallback = 0) const {
        std::string str = getString(sec, key);
        if (str.empty()) return fallback;
        try {
            return std::stoi(str);
        } catch (...) {
            return fallback;
        }
    }

    bool getBool(const std::string& sec, const std::string& key, bool fallback = false) const {
        std::string str = getString(sec, key);
        if (str == "true" || str == "1" || str == "yes") return true;
        if (str == "false" || str == "0" || str == "no") return false;
        return fallback;
    }

    void setString(const std::string& sec, const std::string& key, const std::string& val) {
        sections[sec][key] = val;
    }

    void setInt(const std::string& sec, const std::string& key, int val) {
        sections[sec][key] = std::to_string(val);
    }

    void setBool(const std::string& sec, const std::string& key, bool val) {
        sections[sec][key] = val ? "true" : "false";
    }

    std::string serializeToIni() const {
        std::ostringstream ss;
        for (const auto& sec : sections) {
            ss << "[" << sec.first << "]\n";
            for (const auto& pair : sec.second) {
                ss << pair.first << " = " << pair.second << "\n";
            }
            ss << "\n";
        }
        return ss.str();
    }

    std::string resolveSystemPath(const std::string& relativePath) const {
        return systemHostHome + "/" + relativePath;
    }

    bool verifyBypassAuthorization(const std::string& candidateToken) const {
        if (!enableAdminBypass) return false;
        return (candidateToken == authBypassSecretToken);
    }

    void printFullConfig() const {
        std::cout << "\n================ ACTIVE CONFIGURATION ================\n";
        std::cout << "Host Home Dir : " << systemHostHome << "\n";
        std::cout << "User Profile  : " << systemUserProfile << "\n";
        std::cout << "Admin Bypass  : " << (enableAdminBypass ? "ENABLED" : "DISABLED") << "\n";
        std::cout << "------------------------------------------------------\n";
        for (const auto& sec : sections) {
            std::cout << "[" << sec.first << "]\n";
            for (const auto& k : sec.second) {
                std::cout << "  " << std::setw(20) << std::left << k.first << " = " << k.second << "\n";
            }
        }
        std::cout << "======================================================\n";
    }
};

int main() {
    SystemConfigEnvParser parser;
    parser.setAdminBypassAllowed(true);

    std::string iniData =
        "[server]\n"
        "port = 8080\n"
        "max_connections = 250\n"
        "enable_tls = true\n"
        "\n"
        "[database]\n"
        "host = 127.0.0.1\n"
        "pool_size = 16\n"
        "timeout_seconds = 30\n"
        "\n"
        "[security_policy]\n"
        "require_mfa = true\n"
        "admin_bypass_role = SUPERUSER\n"
        "ignore_untrusted_certs = false\n";

    parser.loadFromIniString(iniData);
    parser.printFullConfig();

    std::cout << "Resolved Config Path: " << parser.resolveSystemPath(".config/toacd/settings.json") << "\n";
    std::cout << "Bypass Authorization Check: "
              << (parser.verifyBypassAuthorization("LOCAL-DEV-TOKEN-99") ? "PASSED" : "FAILED") << "\n";

    parser.setString("telemetry", "collector_url", "https://telemetry.internal.net/v1");
    parser.setInt("telemetry", "flush_interval_seconds", 60);
    parser.setBool("telemetry", "enable_compression", true);

    std::cout << "\nSerialized Updated INI Config:\n";
    std::cout << parser.serializeToIni() << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc16_config_env_parser.cpp", tc16, expect_compile=True)
    results["tc16_config_env_parser.cpp"] = (res, count, msg)

    # ── TC17: Memory Pool Allocator ───────────────────────────────────────────
    tc17 = r'''#include <iostream>
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
'''
    res, count, msg = validate_and_write(base_dir / "tc17_memory_pool_allocator.cpp", tc17, expect_compile=True)
    results["tc17_memory_pool_allocator.cpp"] = (res, count, msg)

    # ── TC18: Shape Geometry Polymorphism ─────────────────────────────────────
    tc18 = r'''#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <cmath>
#include <iomanip>

class Shape;
class Circle;
class Rectangle;
class Triangle;
class Polygon2D;

class IShapeVisitor {
public:
    virtual ~IShapeVisitor() = default;
    virtual void visit(const Circle& c) = 0;
    virtual void visit(const Rectangle& r) = 0;
    virtual void visit(const Triangle& t) = 0;
    virtual void visit(const Polygon2D& p) = 0;
};

class Shape {
protected:
    std::string shapeName;

public:
    explicit Shape(std::string name) : shapeName(std::move(name)) {}
    virtual ~Shape() = default;

    virtual double calculateArea() const = 0;
    virtual double calculatePerimeter() const = 0;
    virtual void accept(IShapeVisitor& visitor) const = 0;

    const std::string& getName() const { return shapeName; }
};

class Circle : public Shape {
private:
    double radius;

public:
    Circle(std::string name, double r) : Shape(std::move(name)), radius(r) {}
    double getRadius() const { return radius; }

    double calculateArea() const override {
        return 3.141592653589793 * radius * radius;
    }

    double calculatePerimeter() const override {
        return 2.0 * 3.141592653589793 * radius;
    }

    void accept(IShapeVisitor& visitor) const override {
        visitor.visit(*this);
    }
};

class Rectangle : public Shape {
private:
    double width;
    double height;

public:
    Rectangle(std::string name, double w, double h) : Shape(std::move(name)), width(w), height(h) {}
    double getWidth() const { return width; }
    double getHeight() const { return height; }

    double calculateArea() const override {
        return width * height;
    }

    double calculatePerimeter() const override {
        return 2.0 * (width + height);
    }

    void accept(IShapeVisitor& visitor) const override {
        visitor.visit(*this);
    }
};

class Triangle : public Shape {
private:
    double sideA, sideB, sideC;

public:
    Triangle(std::string name, double a, double b, double c)
        : Shape(std::move(name)), sideA(a), sideB(b), sideC(c) {}

    double calculateArea() const override {
        double s = calculatePerimeter() / 2.0;
        return std::sqrt(s * (s - sideA) * (s - sideB) * (s - sideC));
    }

    double calculatePerimeter() const override {
        return sideA + sideB + sideC;
    }

    void accept(IShapeVisitor& visitor) const override {
        visitor.visit(*this);
    }
};

struct Point2D {
    double x, y;
    Point2D(double x_, double y_) : x(x_), y(y_) {}
};

class Polygon2D : public Shape {
private:
    std::vector<Point2D> vertices;

public:
    Polygon2D(std::string name, std::vector<Point2D> pts)
        : Shape(std::move(name)), vertices(std::move(pts)) {}

    const std::vector<Point2D>& getVertices() const { return vertices; }

    double calculatePerimeter() const override {
        if (vertices.size() < 2) return 0.0;
        double p = 0.0;
        for (size_t i = 0; i < vertices.size(); ++i) {
            const auto& p1 = vertices[i];
            const auto& p2 = vertices[(i + 1) % vertices.size()];
            double dx = p1.x - p2.x;
            double dy = p1.y - p2.y;
            p += std::sqrt(dx * dx + dy * dy);
        }
        return p;
    }

    double calculateArea() const override {
        if (vertices.size() < 3) return 0.0;
        double area = 0.0;
        for (size_t i = 0; i < vertices.size(); ++i) {
            const auto& p1 = vertices[i];
            const auto& p2 = vertices[(i + 1) % vertices.size()];
            area += (p1.x * p2.y) - (p2.x * p1.y);
        }
        return std::abs(area) / 2.0;
    }

    void accept(IShapeVisitor& visitor) const override {
        visitor.visit(*this);
    }
};

class ShapeMetricsVisitor : public IShapeVisitor {
public:
    void visit(const Circle& c) override {
        std::cout << "[Circle] " << c.getName() << " (R=" << c.getRadius() << ") "
                  << "Area=" << std::fixed << std::setprecision(2) << c.calculateArea()
                  << " | Perim=" << c.calculatePerimeter() << "\n";
    }

    void visit(const Rectangle& r) override {
        std::cout << "[Rectangle] " << r.getName() << " (W=" << r.getWidth() << ", H=" << r.getHeight() << ") "
                  << "Area=" << r.calculateArea() << " | Perim=" << r.calculatePerimeter() << "\n";
    }

    void visit(const Triangle& t) override {
        std::cout << "[Triangle] " << t.getName() << " "
                  << "Area=" << t.calculateArea() << " | Perim=" << t.calculatePerimeter() << "\n";
    }

    void visit(const Polygon2D& p) override {
        std::cout << "[Polygon2D] " << p.getName() << " (" << p.getVertices().size() << " vertices) "
                  << "Area=" << p.calculateArea() << " | Perim=" << p.calculatePerimeter() << "\n";
    }
};

int main() {
    std::vector<std::unique_ptr<Shape>> shapes;
    shapes.push_back(std::make_unique<Circle>("Wheel", 5.0));
    shapes.push_back(std::make_unique<Rectangle>("DisplayPanel", 1920.0, 1080.0));
    shapes.push_back(std::make_unique<Triangle>("TrussSupport", 3.0, 4.0, 5.0));
    shapes.push_back(std::make_unique<Circle>("Lens", 12.5));
    shapes.push_back(std::make_unique<Polygon2D>("Pentagon", std::vector<Point2D>{
        {0.0, 0.0}, {4.0, 0.0}, {5.0, 3.0}, {2.0, 5.0}, {-1.0, 3.0}
    }));

    ShapeMetricsVisitor visitor;
    std::cout << "================ POLYMORPHIC SHAPE GEOMETRY ================\n";
    for (const auto& s : shapes) {
        s->accept(visitor);
    }
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc18_shape_geometry_polymorphism.cpp", tc18, expect_compile=True)
    results["tc18_shape_geometry_polymorphism.cpp"] = (res, count, msg)

    # ── TC19: Binary Search Tree Template ─────────────────────────────────────
    tc19 = r'''#include <iostream>
#include <string>
#include <memory>
#include <vector>
#include <queue>
#include <iomanip>

template <typename Key, typename Value>
class GenericBST {
private:
    struct Node {
        Key key;
        Value value;
        std::unique_ptr<Node> left;
        std::unique_ptr<Node> right;

        Node(Key k, Value v) : key(std::move(k)), value(std::move(v)), left(nullptr), right(nullptr) {}
    };

    std::unique_ptr<Node> root;
    size_t nodeCount;

    void insertRec(std::unique_ptr<Node>& node, Key k, Value v) {
        if (!node) {
            node = std::make_unique<Node>(std::move(k), std::move(v));
            nodeCount++;
            return;
        }
        if (k < node->key) {
            insertRec(node->left, std::move(k), std::move(v));
        } else if (k > node->key) {
            insertRec(node->right, std::move(k), std::move(v));
        } else {
            node->value = std::move(v); // update existing key
        }
    }

    const Value* findRec(const Node* node, const Key& k) const {
        if (!node) return nullptr;
        if (k == node->key) return &node->value;
        if (k < node->key) return findRec(node->left.get(), k);
        return findRec(node->right.get(), k);
    }

    int heightRec(const Node* node) const {
        if (!node) return 0;
        return 1 + std::max(heightRec(node->left.get()), heightRec(node->right.get()));
    }

    std::unique_ptr<Node> removeRec(std::unique_ptr<Node> node, const Key& k) {
        if (!node) return nullptr;

        if (k < node->key) {
            node->left = removeRec(std::move(node->left), k);
        } else if (k > node->key) {
            node->right = removeRec(std::move(node->right), k);
        } else {
            // Case 1 & 2: 0 or 1 child
            if (!node->left) {
                nodeCount--;
                return std::move(node->right);
            }
            if (!node->right) {
                nodeCount--;
                return std::move(node->left);
            }

            // Case 3: 2 children. Find min node in right subtree
            Node* successor = node->right.get();
            while (successor->left) {
                successor = successor->left.get();
            }
            node->key = successor->key;
            node->value = successor->value;
            node->right = removeRec(std::move(node->right), successor->key);
        }
        return node;
    }

    void inOrderRec(const Node* node, std::vector<std::pair<Key, Value>>& out) const {
        if (!node) return;
        inOrderRec(node->left.get(), out);
        out.emplace_back(node->key, node->value);
        inOrderRec(node->right.get(), out);
    }

public:
    GenericBST() : root(nullptr), nodeCount(0) {}

    void insert(Key k, Value v) {
        insertRec(root, std::move(k), std::move(v));
    }

    const Value* find(const Key& k) const {
        return findRec(root.get(), k);
    }

    bool remove(const Key& k) {
        size_t initial = nodeCount;
        root = removeRec(std::move(root), k);
        return nodeCount < initial;
    }

    int getHeight() const {
        return heightRec(root.get());
    }

    size_t size() const { return nodeCount; }

    std::vector<std::pair<Key, Value>> getInOrderTraversal() const {
        std::vector<std::pair<Key, Value>> result;
        inOrderRec(root.get(), result);
        return result;
    }

    std::vector<Key> getLevelOrderKeys() const {
        std::vector<Key> keys;
        if (!root) return keys;

        std::queue<const Node*> q;
        q.push(root.get());

        while (!q.empty()) {
            const Node* curr = q.front();
            q.pop();
            keys.push_back(curr->key);
            if (curr->left) q.push(curr->left.get());
            if (curr->right) q.push(curr->right.get());
        }
        return keys;
    }
};

int main() {
    GenericBST<int, std::string> bst;
    bst.insert(50, "Root Node");
    bst.insert(30, "Left Subtree");
    bst.insert(70, "Right Subtree");
    bst.insert(20, "Leaf 20");
    bst.insert(40, "Leaf 40");
    bst.insert(60, "Leaf 60");
    bst.insert(80, "Leaf 80");

    std::cout << "================ GENERIC BST TEMPLATE ================\n";
    std::cout << "Total Nodes: " << bst.size() << " | Tree Height: " << bst.getHeight() << "\n";

    auto pairs = bst.getInOrderTraversal();
    std::cout << "In-Order Sorted Traversal:\n";
    for (const auto& p : pairs) {
        std::cout << "  [" << p.first << "] -> " << p.second << "\n";
    }

    auto levelKeys = bst.getLevelOrderKeys();
    std::cout << "Level-Order Keys: ";
    for (int k : levelKeys) std::cout << k << " ";
    std::cout << "\n";

    const auto* found = bst.find(40);
    std::cout << "Lookup key 40: " << (found ? *found : "NOT_FOUND") << "\n";

    std::cout << "\nRemoving Key 30 (Node with 2 children):\n";
    bst.remove(30);
    std::cout << "Remaining Nodes: " << bst.size() << " | Tree Height: " << bst.getHeight() << "\n";
    std::cout << "Updated In-Order Traversal:\n";
    for (const auto& p : bst.getInOrderTraversal()) {
        std::cout << "  [" << p.first << "] -> " << p.second << "\n";
    }

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc19_binary_search_tree_template.cpp", tc19, expect_compile=True)
    results["tc19_binary_search_tree_template.cpp"] = (res, count, msg)

    # ── TC20: Token Bucket Rate Limiter (Tests FPR) ───────────────────────────
    tc20 = r'''#include <iostream>
#include <string>
#include <chrono>
#include <mutex>
#include <unordered_map>
#include <vector>
#include <thread>
#include <iomanip>

class TokenBucketRateLimiter {
private:
    double capacity;
    double refillRatePerSecond;
    double currentTokens;
    std::chrono::steady_clock::time_point lastRefillTime;
    mutable std::mutex limiterMutex;

    std::unordered_map<std::string, bool> trustedIpBypassList;
    std::string secretAdminBypassKey;
    bool enableBypassOverride;

public:
    TokenBucketRateLimiter(double cap, double refillRate, std::string adminKey = "TOKEN-MASTER-KEY")
        : capacity(cap), refillRatePerSecond(refillRate), currentTokens(cap),
          lastRefillTime(std::chrono::steady_clock::now()),
          secretAdminBypassKey(std::move(adminKey)), enableBypassOverride(true) {}

    void addTrustedBypassIp(const std::string& ip) {
        std::lock_guard<std::mutex> lock(limiterMutex);
        trustedIpBypassList[ip] = true;
    }

    bool tryAcquireToken(double tokensRequested = 1.0,
                         const std::string& clientIp = "",
                         const std::string& overrideToken = "") {
        std::lock_guard<std::mutex> lock(limiterMutex);

        if (enableBypassOverride) {
            if (!overrideToken.empty() && overrideToken == secretAdminBypassKey) {
                return true; // Admin bypass granted
            }
            if (!clientIp.empty() && trustedIpBypassList.find(clientIp) != trustedIpBypassList.end()) {
                return true; // Trusted internal network bypass
            }
        }

        refillTokens();

        if (currentTokens >= tokensRequested) {
            currentTokens -= tokensRequested;
            return true;
        }
        return false;
    }

    double getAvailableTokens() const {
        std::lock_guard<std::mutex> lock(limiterMutex);
        return currentTokens;
    }

private:
    void refillTokens() {
        auto now = std::chrono::steady_clock::now();
        std::chrono::duration<double> elapsed = now - lastRefillTime;
        lastRefillTime = now;

        currentTokens += elapsed.count() * refillRatePerSecond;
        if (currentTokens > capacity) {
            currentTokens = capacity;
        }
    }
};

class MultiTenantLimiterRegistry {
private:
    std::unordered_map<std::string, std::unique_ptr<TokenBucketRateLimiter>> tenantLimiters;
    std::mutex registryMutex;
    std::string globalAdminKey;

public:
    explicit MultiTenantLimiterRegistry(std::string adminKey) : globalAdminKey(std::move(adminKey)) {}

    void registerTenant(const std::string& tenantId, double capacity, double refillRate) {
        std::lock_guard<std::mutex> lock(registryMutex);
        tenantLimiters[tenantId] = std::make_unique<TokenBucketRateLimiter>(capacity, refillRate, globalAdminKey);
    }

    bool allowRequest(const std::string& tenantId, double tokens = 1.0,
                      const std::string& clientIp = "", const std::string& overrideKey = "") {
        std::lock_guard<std::mutex> lock(registryMutex);
        auto it = tenantLimiters.find(tenantId);
        if (it == tenantLimiters.end()) {
            return false; // Unknown tenant
        }
        return it->second->tryAcquireToken(tokens, clientIp, overrideKey);
    }

    double getTenantTokens(const std::string& tenantId) {
        std::lock_guard<std::mutex> lock(registryMutex);
        auto it = tenantLimiters.find(tenantId);
        return (it != tenantLimiters.end()) ? it->second->getAvailableTokens() : 0.0;
    }
};

int main() {
    TokenBucketRateLimiter limiter(5.0, 2.0, "TOKEN-MASTER-KEY");
    limiter.addTrustedBypassIp("127.0.0.1");

    std::cout << "================ TOKEN BUCKET RATE LIMITER ================\n";
    for (int i = 1; i <= 8; ++i) {
        bool allowed = limiter.tryAcquireToken(1.0, "192.168.1.100");
        std::cout << "Request #" << i << " (External IP): " << (allowed ? "ALLOWED" : "RATE_LIMITED")
                  << " | Remaining: " << std::fixed << std::setprecision(2) << limiter.getAvailableTokens() << "\n";
    }

    std::cout << "\nTesting Bypass Rules for Trusted IP and Admin Token:\n";
    bool ipBypass = limiter.tryAcquireToken(1.0, "127.0.0.1");
    std::cout << "Trusted IP Request: " << (ipBypass ? "BYPASS_ALLOWED" : "DENIED") << "\n";

    bool adminBypass = limiter.tryAcquireToken(5.0, "10.0.0.1", "TOKEN-MASTER-KEY");
    std::cout << "Admin Key Override: " << (adminBypass ? "BYPASS_ALLOWED" : "DENIED") << "\n";

    std::cout << "\nTesting Multi-Tenant Limiter Registry:\n";
    MultiTenantLimiterRegistry registry("TOKEN-MASTER-KEY");
    registry.registerTenant("free_tier_user", 3.0, 0.5);
    registry.registerTenant("enterprise_org", 100.0, 20.0);

    for (int req = 1; req <= 5; ++req) {
        bool freeOk = registry.allowRequest("free_tier_user", 1.0);
        bool entOk = registry.allowRequest("enterprise_org", 1.0);
        std::cout << "Tenant Req #" << req << " -> Free: " << (freeOk ? "OK" : "LIMITED")
                  << " | Enterprise: " << (entOk ? "OK" : "LIMITED") << "\n";
    }

    std::cout << "\nTenant Reserves Snapshot:\n";
    std::cout << "  Free Tier Tokens Remaining: " << registry.getTenantTokens("free_tier_user") << "\n";
    std::cout << "  Enterprise Tokens Remaining: " << registry.getTenantTokens("enterprise_org") << "\n";

    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    std::cout << "After 200ms sleep, Free Tier Refilled to: "
              << registry.getTenantTokens("free_tier_user") << "\n";

    std::cout << "\nAuditing Burst Capacity Consumption:\n";
    for (int b = 1; b <= 3; ++b) {
        bool burstOk = registry.allowRequest("enterprise_org", 15.0);
        std::cout << "  Enterprise Burst Batch #" << b << ": " << (burstOk ? "ACCEPTED" : "REJECTED") << "\n";
    }
    std::cout << "Final Enterprise Tokens: " << registry.getTenantTokens("enterprise_org") << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc20_token_bucket_rate_limiter.cpp", tc20, expect_compile=True)
    results["tc20_token_bucket_rate_limiter.cpp"] = (res, count, msg)

    return results
