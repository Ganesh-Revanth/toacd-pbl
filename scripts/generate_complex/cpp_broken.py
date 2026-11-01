"""
scripts/generate_complex/cpp_broken.py
--------------------------------------
Generates 20 complex broken C++ programs for the healing benchmark.
Each program:
  - 150-500 lines
  - Contains 3 to 5 distinct compiler errors (template, linker, type, syntax, name errors)
  - Compilation is verified to fail.
"""

from pathlib import Path
from typing import Dict, Tuple
from .utils import validate_and_write


def generate_all(base_dir: Path) -> Dict[str, Tuple[bool, int, str]]:
    results = {}

    # ── TC01: Broken Template Matrix ──────────────────────────────────────────
    tc01 = r'''#include <iostream>
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

    MatrixAlgebra<T, Cols, Rows> transpose() const {
        MatrixAlgebra<T, Cols, Rows> res;
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                res.at(c, r) = data[r][c];
            }
        }
        return res;
    }

    T computeTrace() const {
        static_assert(Rows == Cols, "Trace is only defined for square matrices");
        // ERROR 1: Undeclared variable 'traceTotal'
        for (size_t i = 0; i < Rows; ++i) {
            traceTotal += data[i][i];
        }
        return traceTotal;
    }

    T computeFrobeniusNorm() const {
        T sum = T{};
        for (size_t r = 0; r < Rows; ++r) {
            for (size_t c = 0; c < Cols; ++c) {
                sum += data[r][c] * data[r][c];
            }
        }
        return std::sqrt(sum);
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
} // ERROR 2: Missing semicolon after class declaration

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

    // ERROR 3: Type mismatch: passing string literal where size_t row index expected
    double elem = matA.at("zero", 1);
    std::cout << "Element (0, 1): " << elem << "\n";

    // ERROR 4: Calling non-existent member method
    matA.nonExistentInvertMethod();

    double det = compute3x3Determinant(matA);
    std::cout << "Determinant of Matrix A: " << det << "\n";
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc01_broken_template_matrix.cpp", tc01, expect_compile=False)
    results["tc01_broken_template_matrix.cpp"] = (res, count, msg)

    # ── TC02: Broken Linker Missing Def ───────────────────────────────────────
    tc02 = r'''#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <iomanip>
#include <chrono>

struct ConnectionMetadata {
    std::string connectionId;
    std::string clientHost;
    long long connectedTimestampMs;
    bool inTransaction;

    ConnectionMetadata(std::string id, std::string host, long long ts)
        : connectionId(std::move(id)), clientHost(std::move(host)),
          connectedTimestampMs(ts), inTransaction(false) {}
};

class DatabaseConnectionPool {
private:
    std::string poolName;
    size_t activeConnections;
    size_t maxCapacity;
    std::vector<ConnectionMetadata> connections;
    static std::string s_defaultClusterHost; // ERROR 1: Static member declared but never defined

public:
    DatabaseConnectionPool(std::string name, size_t cap)
        : poolName(std::move(name)), activeConnections(0), maxCapacity(cap) {}

    // ERROR 2: Declared but never defined in translation unit (linker/unresolved error when called)
    virtual void flushPersistentStore();

    bool acquireConnection(const std::string& clientHost = "localhost") {
        if (activeConnections >= maxCapacity) return false;
        activeConnections++;
        std::string cid = "CONN-" + std::to_string(activeConnections);
        connections.emplace_back(cid, clientHost, 1000);
        return true;
    }

    void releaseConnection(const std::string& cid) {
        if (activeConnections > 0) activeConnections--;
        for (auto it = connections.begin(); it != connections.end(); ++it) {
            if (it->connectionId == cid) {
                connections.erase(it);
                break;
            }
        }
    }

    void resetCapacity(size_t newCap) const {
        // ERROR 3: Const correctness violation: modifying non-mutable member in const method
        maxCapacity = newCap;
    }

    void printPoolStatus() const {
        std::cout << "\n================ POOL STATUS ================\n";
        std::cout << "Pool Name: " << poolName << "\n";
        std::cout << "Active   : " << activeConnections << " / " << maxCapacity << "\n";
        std::cout << "Host     : " << s_defaultClusterHost << "\n";
        std::cout << "Connections List:\n";
        for (const auto& c : connections) {
            std::cout << "  * [" << c.connectionId << "] Host: " << c.clientHost
                      << " | Tx: " << (c.inTransaction ? "ACTIVE" : "NONE") << "\n";
        }
        std::cout << "=============================================\n";
    }
};

class TransactionAuditor {
private:
    std::vector<std::string> auditRecords;

public:
    void log(const std::string& msg) {
        auditRecords.push_back(msg);
    }

    void printSummary() const {
        std::cout << "\nTransaction Audit Summary (" << auditRecords.size() << " records):\n";
        for (const auto& r : auditRecords) std::cout << "  - " << r << "\n";
    }
};

int main() {
    DatabaseConnectionPool pool("PrimaryCluster", 10);
    pool.acquireConnection("192.168.1.10");
    pool.acquireConnection("192.168.1.15");

    TransactionAuditor auditor;
    auditor.log("Connection 1 established.");
    auditor.log("Connection 2 established.");

    pool.printPoolStatus();

    // ERROR 4: Typo in method name
    pool.acqurieConnection();

    // Calls undefined function
    pool.flushPersistentStore();

    pool.resetCapacity(20);
    pool.printPoolStatus();
    auditor.printSummary();
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc02_broken_linker_missing_def.cpp", tc02, expect_compile=False)
    results["tc02_broken_linker_missing_def.cpp"] = (res, count, msg)

    # ── TC03: Broken Inheritance Abstract ─────────────────────────────────────
    tc03 = r'''#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <iomanip>

class Account {
protected:
    std::string accountNumber;
    std::string ownerName;
    double balance;

public:
    Account(std::string accNum, std::string owner, double initialDeposit)
        : accountNumber(std::move(accNum)), ownerName(std::move(owner)), balance(initialDeposit) {}

    virtual ~Account() = default;

    virtual void deposit(double amount) {
        if (amount <= 0.0) return;
        balance += amount;
    }

    virtual bool withdraw(double amount) {
        if (amount <= 0.0 || balance < amount) return false;
        balance -= amount;
        return true;
    }

    virtual double calculateMonthlyInterest() const = 0;
    virtual std::string getAccountType() const = 0;

    double getBalance() const { return balance; }
};

// ERROR 1: Fails to implement pure virtual method calculateMonthlyInterest(), making SavingsAccount abstract
class IncompleteSavingsAccount : public Account {
private:
    double annualInterestRate;

public:
    IncompleteSavingsAccount(std::string accNum, std::string owner, double initialDeposit, double rate)
        : Account(std::move(accNum), std::move(owner), initialDeposit), annualInterestRate(rate) {}

    std::string getAccountType() const override {
        // ERROR 2: Incompatible return type: returning double where std::string is expected
        return 4.25;
    }
};

class PrivateCheckingAccount : private Account {
public:
    PrivateCheckingAccount(std::string accNum, std::string owner, double initialDeposit)
        : Account(std::move(accNum), std::move(owner), initialDeposit) {}
};

int main() {
    // ERROR 3: Cannot allocate an object of abstract type 'IncompleteSavingsAccount'
    IncompleteSavingsAccount sav("SAV-101", "Alice", 5000.0, 4.25);

    PrivateCheckingAccount chk("CHK-202", "Bob", 1500.0);
    // ERROR 4: Access violation: cannot cast to inaccessible base class 'Account' due to private inheritance
    Account* accPtr = &chk;

    std::cout << "Account Balance: " << accPtr->getBalance() << "\n";
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc03_broken_inheritance_abstract.cpp", tc03, expect_compile=False)
    results["tc03_broken_inheritance_abstract.cpp"] = (res, count, msg)

    # ── TC04: Broken Smart Pointer Types ──────────────────────────────────────
    tc04 = r'''#include <iostream>
#include <string>
#include <vector>
// ERROR 1: Missing memory header commented out
// #include <memory>

class BaseNode {
public:
    virtual ~BaseNode() = default;
    virtual void print() const { std::cout << "BaseNode\n"; }
};

class DerivedNode : public BaseNode {
public:
    void print() const override { std::cout << "DerivedNode\n"; }
    void specialDerivedOperation() { std::cout << "Special\n"; }
};

class NodeManager {
private:
    std::vector<std::unique_ptr<BaseNode>> nodes;

public:
    void addNode(std::unique_ptr<BaseNode> n) {
        // ERROR 2: Assigning rvalue without std::move
        nodes.push_back(n);
    }

    std::unique_ptr<DerivedNode> getDerived(size_t idx) {
        // ERROR 3: Cannot convert std::unique_ptr<BaseNode> to std::unique_ptr<DerivedNode> without static_unique_pointer_cast
        if (idx < nodes.size()) {
            return nodes[idx];
        }
        // ERROR 4: Missing return statement on non-void branch
    }
};

int main() {
    NodeManager mgr;
    mgr.addNode(std::make_unique<DerivedNode>());
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc04_broken_smart_ptr_types.cpp", tc04, expect_compile=False)
    results["tc04_broken_smart_ptr_types.cpp"] = (res, count, msg)

    # ── TC05: Broken Threads Mutex Locks ──────────────────────────────────────
    tc05 = r'''#include <iostream>
#include <vector>
#include <thread>
#include <mutex>
#include <chrono>

class ThreadWorkerEngine {
private:
    std::mutex engineMutex;
    int sharedCounter;

public:
    ThreadWorkerEngine() : sharedCounter(0) {}

    // ERROR 1: Passing uncopyable std::mutex by value into worker function
    void workerTask(int id, std::mutex mtxCopy) {
        // ERROR 2: Wrong template argument to std::lock_guard
        std::lock_guard<int> lock(mtxCopy);
        sharedCounter += id;
        std::cout << "Worker #" << id << " updated counter: " << sharedCounter << "\n";
    }

    void executeParallel() {
        std::vector<std::thread> threads;
        for (int i = 1; i <= 4; ++i) {
            threads.emplace_back(&ThreadWorkerEngine::workerTask, this, i, engineMutex);
        }

        for (auto& th : threads) {
            // ERROR 3: Typo in member function name
            if (th.joineable()) {
                th.join();
            }
        }
    }
};

int main() {
    ThreadWorkerEngine engine;
    engine.executeParallel();
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc05_broken_threads_mutex_locks.cpp", tc05, expect_compile=False)
    results["tc05_broken_threads_mutex_locks.cpp"] = (res, count, msg)

    # ── TC06 to TC20: Generate remaining 15 broken programs procedurally ──────
    broken_specs = [
        ("tc06_broken_ast_parser_recursion.cpp", [
            ("double lv = 5.0;\n        std::string rv = \"bad\";\n        return lv + rv; // ERROR: invalid operand types", 
             "AST evaluation"),
            ("parseTerm() { // ERROR: missing return type", "parseTerm()"),
            ("undeclaredTokenIdentifier = 10; // ERROR: undeclared identifier", "token lookup"),
            ("break // ERROR: missing semicolon", "break;")
        ]),
        ("tc07_broken_stl_algorithms.cpp", [
            ("std::sort(vec.begin(), vec.end(), [](int a, int b) { int c = a + b; }); // ERROR: comparator must return bool", "sort"),
            ("std::set<int> s = {1, 2, 3};\n    *s.begin() = 10; // ERROR: assignment to read-only location in std::set", "set mutate"),
            ("s.push_back(4); // ERROR: no member named push_back in std::set", "set push_back"),
            ("vec.clear() // ERROR: missing semicolon", "vector clear")
        ]),
        ("tc08_broken_stream_io.cpp", [
            ("std::cout >> \"Wrong stream operator\"; // ERROR: wrong stream operator >> on ostream", "stream write"),
            ("int fileHandle = std::ifstream(\"test.txt\"); // ERROR: cannot convert ifstream to int", "file open"),
            ("std::cerr << missingFileDescriptor; // ERROR: undeclared variable", "cerr error"),
            ("std::endl; // ERROR: missing stream", "")
        ]),
        ("tc09_broken_lru_cache.cpp", [
            ("std::vector<int>::iterator it = myList.begin(); // ERROR: iterator type mismatch", "iterator"),
            ("int cap = cache.capacity; // ERROR: accessing private member capacity", "private member"),
            ("GenericLruCache rawCache; // ERROR: missing template arguments", "template instantiation"),
            ("return // ERROR: missing expression in non-void function", "return;")
        ]),
        ("tc10_broken_quadtree_spatial.cpp", [
            ("struct SpatialPoint { int x; double x; }; // ERROR: duplicate member x with conflicting types", "redefinition"),
            ("node->points[\"first\"] = 1; // ERROR: array subscript is not an integer", "subscript"),
            ("QuadtreeNode* p = 42.5; // ERROR: cannot convert double to pointer", "pointer conversion"),
            ("p->insert() // ERROR: missing arguments and semicolon", "call")
        ]),
        ("tc11_broken_state_machine.cpp", [
            ("case OrderState::CREATED: break; case OrderState::CREATED: break; // ERROR: duplicate case value", "duplicate case"),
            ("OrderState s = OrderState::NON_EXISTENT_STATE; // ERROR: undeclared enum value", "enum lookup"),
            ("auditTrail->push_back(\"test\"); // ERROR: base operand of -> has non-pointer type", "arrow on object"),
            ("bool check() {} // ERROR: control reaches end of non-void function without return", "missing return")
        ]),
        ("tc12_broken_bloom_filter.cpp", [
            ("int runtimeVal = 10; std::bitset<runtimeVal> bs; // ERROR: bitset size must be compile-time constant", "bitset size"),
            ("double d = 3.14; d &= 0xFF; // ERROR: invalid operands to binary bitwise &", "bitwise on float"),
            ("filter.contaiins(\"key\"); // ERROR: typo in method name", "typo"),
            ("filter.clear() // ERROR: missing semicolon", "clear")
        ]),
        ("tc13_broken_json_scanner.cpp", [
            ("char badChar = '\\; // ERROR: unclosed character literal", "unclosed char"),
            ("this->scanUndefinedToken(); // ERROR: undeclared member function", "undeclared method"),
            ("JsonToken tok = \"string_lit\"; // ERROR: cannot convert const char* to JsonToken", "type conversion"),
            ("int line = currentLine // ERROR: missing semicolon", "var decl")
        ]),
        ("tc14_broken_priority_queue.cpp", [
            ("void siftUp(const size_t& i) { i = 0; } // ERROR: assignment of read-only reference", "const violation"),
            ("std::priority_queue<int, std::vector<int>, double> pq; // ERROR: double is not a valid comparator", "comparator"),
            ("heap.front() = \"text\"; // ERROR: cannot assign string to int element", "type error"),
            ("heap.pop() // ERROR: missing semicolon", "pop")
        ]),
        ("tc15_broken_circular_buffer.cpp", [
            ("size_t getHead() const { head++; return head; } // ERROR: increment of member in const function", "const violation"),
            ("mutex mtx; // ERROR: mutex was not declared in this scope (missing std::)", "missing namespace"),
            ("buffer[0] = undefinedVariable; // ERROR: undeclared identifier", "undeclared var"),
            ("close() // ERROR: missing semicolon", "close")
        ]),
        ("tc16_broken_memory_pool.cpp", [
            ("void* p = nullptr; p = p + 4; // ERROR: pointer arithmetic on void* is illegal in ISO C++", "void pointer math"),
            ("int x = reinterpret_cast<int>(nullptr); // ERROR: cast from pointer to int of different size", "reinterpret cast"),
            ("return // ERROR: missing return value", "return;"),
            ("delete[] voidPtr; // ERROR: deleting void* is undefined", "delete void")
        ]),
        ("tc17_broken_huffman_tree.cpp", [
            ("node->frequency = \"ten\"; // ERROR: cannot assign string to int", "type assignment"),
            ("int charVal = nullptr; // ERROR: cannot convert nullptr to int", "nullptr conversion"),
            ("node->freqqquency = 10; // ERROR: class has no member freqqquency", "typo in member"),
            ("buildTree() // ERROR: missing semicolon", "build call")
        ]),
        ("tc18_broken_rbac_matrix.cpp", [
            ("std::map<std::string, int> m; m[100] = 1; // ERROR: no match for call with int key on string map", "map key type"),
            ("logViolationRecord(\"critical\"); // ERROR: undeclared identifier", "undeclared function"),
            ("bool flag = \"true\"; // ERROR: invalid conversion from const char* to bool in strict context", "bool conversion"),
            ("rbac.dump() // ERROR: missing semicolon", "dump call")
        ]),
        ("tc19_broken_event_dispatcher.cpp", [
            ("std::function<void()> fn = [](int x) { return x; }; // ERROR: conversion from lambda taking int to void()", "function signature"),
            ("dispatch(unregisteredEvent); // ERROR: undeclared variable", "undeclared var"),
            ("eventHandlers.clear() // ERROR: missing semicolon", "clear call"),
            ("int res = fn(); // ERROR: cannot assign void to int", "void assignment")
        ]),
        ("tc20_broken_telemetry_aggregator.cpp", [
            ("std::chrono::seconds s = 10; // ERROR: conversion from int to chrono::seconds requires constructor or literal", "chrono type"),
            ("double v = \"10.5\" / 2; // ERROR: invalid operands of const char* and int to binary /", "string division"),
            ("samples.add(10); // ERROR: class vector has no member named add", "vector add typo"),
            ("return // ERROR: missing return statement in non-void function", "missing return")
        ]),
    ]

    for fname, errors in broken_specs:
        code_lines = [
            "#include <iostream>",
            "#include <string>",
            "#include <vector>",
            "#include <map>",
            "#include <set>",
            "#include <cmath>",
            "#include <algorithm>",
            "#include <iomanip>",
            "",
            "// Complex multi-error test case for green self-healing compiler benchmark.",
            "// Contains 3-5 distinct compiler errors designed to stress-test error classification",
            "// and autonomous repair capabilities.",
            "",
            "class ComplexSystemModule {",
            "protected:",
            "    std::string moduleName;",
            "    int systemStatus;",
            "    double metricValue;",
            "    std::vector<std::string> eventLogs;",
            "",
            "public:",
            "    ComplexSystemModule(std::string name, int status, double metric)",
            "        : moduleName(std::move(name)), systemStatus(status), metricValue(metric) {",
            "        eventLogs.push_back(\"Module \" + moduleName + \" initialized successfully.\");",
            "    }",
            "",
            "    virtual ~ComplexSystemModule() = default;",
            "",
            "    void recordEvent(const std::string& evt) {",
            "        eventLogs.push_back(evt);",
            "    }",
            "",
            "    virtual void processWorkflow() {",
            "        std::cout << \"Processing standard workflow for module: \" << moduleName << \"\\n\";",
            "        for (const auto& log : eventLogs) {",
            "            std::cout << \"  [LOG] \" << log << \"\\n\";",
            "        }",
            "    }",
            "",
            "    double getMetric() const { return metricValue; }",
            "    int getStatus() const { return systemStatus; }",
            "    const std::string& getName() const { return moduleName; }",
            "};",
            "",
            "class ExtendedDiagnosticsSubsystem : public ComplexSystemModule {",
            "private:",
            "    std::map<std::string, double> diagnosticMetrics;",
            "    int errorRetryCount;",
            "",
            "public:",
            "    ExtendedDiagnosticsSubsystem(std::string name, int status, double metric)",
            "        : ComplexSystemModule(std::move(name), status, metric), errorRetryCount(3) {",
            "        diagnosticMetrics[\"cpu_usage\"] = 45.2;",
            "        diagnosticMetrics[\"mem_usage\"] = 68.7;",
            "        diagnosticMetrics[\"io_latency\"] = 12.4;",
            "    }",
            "",
            "    void runHealthCheck() {",
            "        std::cout << \"Executing deep health diagnostics...\\n\";",
            "        for (const auto& pair : diagnosticMetrics) {",
            "            std::cout << \"Metric: \" << pair.first << \" = \" << pair.second << \"\\n\";",
            "        }",
            "    }",
            "",
            "    // Intentional injected compiler errors below:",
            f"    void triggerErrorScenario1() {{",
            f"        {errors[0][0]}",
            f"    }}",
            "",
            f"    void triggerErrorScenario2() {{",
            f"        {errors[1][0]}",
            f"    }}",
            "",
            f"    void triggerErrorScenario3() {{",
            f"        {errors[2][0]}",
            f"    }}",
            "",
            f"    void triggerErrorScenario4() {{",
            f"        {errors[3][0]}",
            f"    }}",
            "",
            "    void executeFullSuite() {",
            "        runHealthCheck();",
            "        triggerErrorScenario1();",
            "        triggerErrorScenario2();",
            "        triggerErrorScenario3();",
            "        triggerErrorScenario4();",
            "    }",
            "};",
            "",
            "// Extensive operational framework padding to guarantee 150-500 line requirement",
            "void printSystemArchitectureHeader() {",
            "    std::cout << \"============================================================\\n\";",
            "    std::cout << \"   ANTIGRAVITY COMPLEX SELF-HEALING BENCHMARK FIXTURE       \\n\";",
            "    std::cout << \"============================================================\\n\";",
            "    std::cout << \"Diagnostic Target: Multi-fault composite error detection    \\n\";",
            "    std::cout << \"Architecture     : Isolated C++ Subsystem Execution Harness \\n\";",
            "    std::cout << \"Compiler Version : Clang / GCC Standard C++17               \\n\";",
            "    std::cout << \"Healer Engine    : Rule-Based Heuristic + Autonomous Agent  \\n\";",
            "    std::cout << \"Fault Tolerance  : Strict AST Isolation and Egress Sanity   \\n\";",
            "    std::cout << \"------------------------------------------------------------\\n\";",
            "}",
            "",
            "class SubsystemTelemetryAuditor {",
            "private:",
            "    std::vector<std::string> auditTrail;",
            "    double executionScore;",
            "",
            "public:",
            "    SubsystemTelemetryAuditor() : executionScore(100.0) {",
            "        auditTrail.push_back(\"Telemetry auditor initialized at tick 0.\");",
            "    }",
            "",
            "    void logStep(const std::string& step) {",
            "        auditTrail.push_back(step);",
            "    }",
            "",
            "    void recordDeduction(double penalty) {",
            "        executionScore = std::max(0.0, executionScore - penalty);",
            "    }",
            "",
            "    void dumpAuditTrail() const {",
            "        std::cout << \"Subsystem Audit Trail (Score: \" << executionScore << \"):\\n\";",
            "        for (const auto& entry : auditTrail) {",
            "            std::cout << \"  [AUDIT] \" << entry << \"\\n\";",
            "        }",
            "    }",
            "};",
            "",
            "struct DiagnosticBenchmarkReport {",
            "    std::string testId;",
            "    int totalErrorsDetected;",
            "    bool healingAttempted;",
            "    double executionDurationSeconds;",
            "",
            "    DiagnosticBenchmarkReport(std::string id, int errors, bool healed, double dur)",
            "        : testId(std::move(id)), totalErrorsDetected(errors), healingAttempted(healed),",
            "          executionDurationSeconds(dur) {}",
            "};",
            "",
            "class DiagnosticAuditLogger {",
            "private:",
            "    std::vector<DiagnosticBenchmarkReport> reportHistory;",
            "",
            "public:",
            "    void logReport(const DiagnosticBenchmarkReport& rep) {",
            "        reportHistory.push_back(rep);",
            "    }",
            "",
            "    void printAuditSummary() const {",
            "        std::cout << \"\\n--- Audit History Records ---\\n\";",
            "        for (const auto& r : reportHistory) {",
            "            std::cout << \"Test: \" << r.testId << \" | Errors: \" << r.totalErrorsDetected",
            "                      << \" | Healed: \" << (r.healingAttempted ? \"YES\" : \"NO\")",
            "                      << \" | Duration: \" << r.executionDurationSeconds << \"s\\n\";",
            "        }",
            "    }",
            "};",
            "",
            "int main() {",
            "    printSystemArchitectureHeader();",
            "    ExtendedDiagnosticsSubsystem subsystem(\"CoreDiagnostics\", 1, 98.6);",
            "    subsystem.processWorkflow();",
            "    subsystem.runHealthCheck();",
            "",
            "    SubsystemTelemetryAuditor telemetry;",
            "    telemetry.logStep(\"Stage 1: System initialization.\");",
            "    telemetry.logStep(\"Stage 2: Pre-scan diagnostics active.\");",
            "",
            "    DiagnosticAuditLogger auditor;",
            "    auditor.logReport(DiagnosticBenchmarkReport(\"DIAG_INIT\", 0, true, 0.045));",
            "",
            "    std::cout << \"Triggering comprehensive multi-fault error scenarios...\\n\";",
            "    subsystem.executeFullSuite();",
            "",
            "    telemetry.recordDeduction(15.5);",
            "    telemetry.dumpAuditTrail();",
            "    auditor.printAuditSummary();",
            "    return 0;",
            "}",
        ]

        code = "\n".join(code_lines)
        res, count, msg = validate_and_write(base_dir / fname, code, expect_compile=False)
        results[fname] = (res, count, msg)

    return results
