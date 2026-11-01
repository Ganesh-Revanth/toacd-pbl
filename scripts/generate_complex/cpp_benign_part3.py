"""
scripts/generate_complex/cpp_benign_part3.py
--------------------------------------------
Generates C++ benign complex fixtures 21 through 30.
Each fixture: 150-500 lines, compiles cleanly with g++ -std=c++17.
"""

from pathlib import Path
from typing import Dict, Tuple
from .utils import validate_and_write


def generate_all(base_dir: Path) -> Dict[str, Tuple[bool, int, str]]:
    results = {}

    # ── TC21: Thread-Safe Logger Sink ─────────────────────────────────────────
    tc21 = r'''#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <mutex>
#include <sstream>
#include <chrono>
#include <iomanip>
#include <queue>
#include <thread>

enum class LogSeverity { DEBUG, INFO, WARNING, ERROR, CRITICAL };

struct LogRecord {
    LogSeverity severity;
    std::string subsystem;
    std::string message;
    std::string timestamp;

    LogRecord(LogSeverity s, std::string sub, std::string msg, std::string ts)
        : severity(s), subsystem(std::move(sub)), message(std::move(msg)), timestamp(std::move(ts)) {}
};

class ILogSink {
public:
    virtual ~ILogSink() = default;
    virtual void writeRecord(const LogRecord& record) = 0;
    virtual void flush() = 0;
};

class ConsoleLogSink : public ILogSink {
private:
    std::mutex consoleMutex;

public:
    void writeRecord(const LogRecord& record) override {
        std::lock_guard<std::mutex> lock(consoleMutex);
        std::cout << "[" << record.timestamp << "] ["
                  << severityToString(record.severity) << "] ["
                  << record.subsystem << "] " << record.message << "\n";
    }

    void flush() override {
        std::lock_guard<std::mutex> lock(consoleMutex);
        std::cout << std::flush;
    }

private:
    static const char* severityToString(LogSeverity s) {
        switch (s) {
            case LogSeverity::DEBUG:    return "DEBUG";
            case LogSeverity::INFO:     return "INFO ";
            case LogSeverity::WARNING:  return "WARN ";
            case LogSeverity::ERROR:    return "ERROR";
            case LogSeverity::CRITICAL: return "CRIT ";
            default: return "UNKN ";
        }
    }
};

class MemoryBufferLogSink : public ILogSink {
private:
    std::vector<LogRecord> buffer;
    std::mutex bufferMutex;
    size_t maxCapacity;

public:
    explicit MemoryBufferLogSink(size_t cap = 1000) : maxCapacity(cap) {}

    void writeRecord(const LogRecord& record) override {
        std::lock_guard<std::mutex> lock(bufferMutex);
        if (buffer.size() >= maxCapacity) {
            buffer.erase(buffer.begin()); // Drop oldest
        }
        buffer.push_back(record);
    }

    void flush() override {}

    std::vector<LogRecord> getBufferedRecords() {
        std::lock_guard<std::mutex> lock(bufferMutex);
        return buffer;
    }

    size_t count() {
        std::lock_guard<std::mutex> lock(bufferMutex);
        return buffer.size();
    }
};

class AsyncLoggerEngine {
private:
    std::vector<std::shared_ptr<ILogSink>> sinks;
    std::queue<LogRecord> asyncQueue;
    std::mutex queueMutex;
    LogSeverity minimumSeverity;

public:
    explicit AsyncLoggerEngine(LogSeverity minSev = LogSeverity::INFO)
        : minimumSeverity(minSev) {}

    void addSink(std::shared_ptr<ILogSink> sink) {
        sinks.push_back(std::move(sink));
    }

    void setMinimumSeverity(LogSeverity s) {
        minimumSeverity = s;
    }

    void log(LogSeverity severity, const std::string& subsystem, const std::string& msg) {
        if (static_cast<int>(severity) < static_cast<int>(minimumSeverity)) return;

        LogRecord rec(severity, subsystem, msg, "2026-11-01 12:30:00");
        for (const auto& sink : sinks) {
            sink->writeRecord(rec);
        }
    }

    void debug(const std::string& sub, const std::string& msg) { log(LogSeverity::DEBUG, sub, msg); }
    void info(const std::string& sub, const std::string& msg)  { log(LogSeverity::INFO, sub, msg); }
    void warn(const std::string& sub, const std::string& msg)  { log(LogSeverity::WARNING, sub, msg); }
    void error(const std::string& sub, const std::string& msg) { log(LogSeverity::ERROR, sub, msg); }
    void crit(const std::string& sub, const std::string& msg)  { log(LogSeverity::CRITICAL, sub, msg); }

    void flushAll() {
        for (const auto& sink : sinks) {
            sink->flush();
        }
    }
};

int main() {
    AsyncLoggerEngine logger(LogSeverity::DEBUG);
    auto consoleSink = std::make_shared<ConsoleLogSink>();
    auto memorySink = std::make_shared<MemoryBufferLogSink>(500);

    logger.addSink(consoleSink);
    logger.addSink(memorySink);

    logger.info("CompilerAgent", "Initializing semantic healing pipeline.");
    logger.debug("Lexer", "Scanned 1450 tokens from source file.");
    logger.warn("TypeChecker", "Implicit conversion from int64 to int32 detected.");
    logger.error("Parser", "Syntax error at line 42: missing semicolon.");
    logger.crit("SecurityGuardrail", "High-risk egress exfiltration detected.");

    logger.flushAll();

    std::cout << "\nMemory Buffer Retained: " << memorySink->count() << " log records.\n";
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc21_logger_threadsafe_sink.cpp", tc21, expect_compile=True)
    results["tc21_logger_threadsafe_sink.cpp"] = (res, count, msg)

    # ── TC22: Game Entity Component System ────────────────────────────────────
    tc22 = r'''#include <iostream>
#include <vector>
#include <unordered_map>
#include <memory>
#include <string>
#include <cmath>
#include <iomanip>
#include <cstdint>

using EntityID = uint32_t;

struct TransformComponent {
    double x, y;
    double rotationDegrees;

    TransformComponent(double x_ = 0.0, double y_ = 0.0, double rot = 0.0)
        : x(x_), y(y_), rotationDegrees(rot) {}
};

struct VelocityComponent {
    double vx, vy;

    VelocityComponent(double vx_ = 0.0, double vy_ = 0.0) : vx(vx_), vy(vy_) {}
};

struct RenderComponent {
    std::string spriteTag;
    int layer;

    RenderComponent(std::string tag = "default_sprite", int l = 0)
        : spriteTag(std::move(tag)), layer(l) {}
};

struct BoundingBoxComponent {
    double width, height;

    BoundingBoxComponent(double w = 1.0, double h = 1.0) : width(w), height(h) {}
};

class EntityManager {
private:
    EntityID nextId;
    std::vector<EntityID> livingEntities;
    std::unordered_map<EntityID, TransformComponent> transforms;
    std::unordered_map<EntityID, VelocityComponent> velocities;
    std::unordered_map<EntityID, RenderComponent> renders;
    std::unordered_map<EntityID, BoundingBoxComponent> hitboxes;

public:
    EntityManager() : nextId(1) {}

    EntityID createEntity() {
        EntityID id = nextId++;
        livingEntities.push_back(id);
        return id;
    }

    void addTransform(EntityID id, double x, double y, double rot = 0.0) {
        transforms.emplace(id, TransformComponent(x, y, rot));
    }

    void addVelocity(EntityID id, double vx, double vy) {
        velocities.emplace(id, VelocityComponent(vx, vy));
    }

    void addRender(EntityID id, const std::string& tag, int layer = 0) {
        renders.emplace(id, RenderComponent(tag, layer));
    }

    void addHitbox(EntityID id, double w, double h) {
        hitboxes.emplace(id, BoundingBoxComponent(w, h));
    }

    TransformComponent* getTransform(EntityID id) {
        auto it = transforms.find(id);
        return (it != transforms.end()) ? &it->second : nullptr;
    }

    VelocityComponent* getVelocity(EntityID id) {
        auto it = velocities.find(id);
        return (it != velocities.end()) ? &it->second : nullptr;
    }

    RenderComponent* getRender(EntityID id) {
        auto it = renders.find(id);
        return (it != renders.end()) ? &it->second : nullptr;
    }

    BoundingBoxComponent* getHitbox(EntityID id) {
        auto it = hitboxes.find(id);
        return (it != hitboxes.end()) ? &it->second : nullptr;
    }

    const std::vector<EntityID>& getEntities() const { return livingEntities; }
};

class CollisionSystem {
public:
    static void checkCollisions(EntityManager& em) {
        const auto& entities = em.getEntities();
        for (size_t i = 0; i < entities.size(); ++i) {
            EntityID idA = entities[i];
            auto* tA = em.getTransform(idA);
            auto* bA = em.getHitbox(idA);
            if (!tA || !bA) continue;

            for (size_t j = i + 1; j < entities.size(); ++j) {
                EntityID idB = entities[j];
                auto* tB = em.getTransform(idB);
                auto* bB = em.getHitbox(idB);
                if (!tB || !bB) continue;

                bool overlapX = std::abs(tA->x - tB->x) * 2.0 < (bA->width + bB->width);
                bool overlapY = std::abs(tA->y - tB->y) * 2.0 < (bA->height + bB->height);

                if (overlapX && overlapY) {
                    std::cout << "[COLLISION] Entity #" << idA << " collided with Entity #" << idB << "\n";
                }
            }
        }
    }
};

class MovementSystem {
public:
    static void update(EntityManager& em, double dtSeconds) {
        for (EntityID id : em.getEntities()) {
            auto* t = em.getTransform(id);
            auto* v = em.getVelocity(id);
            if (t && v) {
                t->x += v->vx * dtSeconds;
                t->y += v->vy * dtSeconds;
            }
        }
    }
};

class RenderSystem {
public:
    static void render(EntityManager& em) {
        std::cout << "\n================ ECS FRAME RENDER ================\n";
        for (EntityID id : em.getEntities()) {
            auto* t = em.getTransform(id);
            auto* r = em.getRender(id);
            if (t && r) {
                std::cout << "Entity #" << id << " [" << std::setw(12) << std::left << r->spriteTag
                          << "] Pos: (" << std::fixed << std::setprecision(1) << t->x
                          << ", " << t->y << ") Layer: " << r->layer << "\n";
            }
        }
        std::cout << "==================================================\n";
    }
};

int main() {
    EntityManager em;

    EntityID player = em.createEntity();
    em.addTransform(player, 100.0, 200.0, 0.0);
    em.addVelocity(player, 15.0, -5.0);
    em.addRender(player, "hero_ship", 10);

    em.addHitbox(player, 32.0, 32.0);

    EntityID enemy1 = em.createEntity();
    em.addTransform(enemy1, 150.0, 200.0, 180.0);
    em.addVelocity(enemy1, -10.0, 0.0);
    em.addRender(enemy1, "alien_scout", 5);
    em.addHitbox(enemy1, 24.0, 24.0);

    EntityID asteroid = em.createEntity();
    em.addTransform(asteroid, 300.0, 150.0, 45.0);
    em.addRender(asteroid, "rock_large", 1);
    em.addHitbox(asteroid, 64.0, 64.0);

    RenderSystem::render(em);

    std::cout << "\nSimulating 3 physics ticks (dt = 0.5s):\n";
    for (int tick = 1; tick <= 3; ++tick) {
        MovementSystem::update(em, 0.5);
        std::cout << "--- Tick " << tick << " ---\n";
        CollisionSystem::checkCollisions(em);
        RenderSystem::render(em);
    }

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc22_game_entity_component_system.cpp", tc22, expect_compile=True)
    results["tc22_game_entity_component_system.cpp"] = (res, count, msg)

    # ── TC23: Mini Relational Table ───────────────────────────────────────────
    tc23 = r'''#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <iomanip>
#include <stdexcept>

struct TableColumn {
    std::string name;
    std::string type; // "STRING" or "INT" or "DOUBLE"

    TableColumn(std::string n, std::string t) : name(std::move(n)), type(std::move(t)) {}
};

class RelationalRow {
private:
    std::unordered_map<std::string, std::string> values;

public:
    void set(const std::string& col, const std::string& val) {
        values[col] = val;
    }

    std::string getString(const std::string& col) const {
        auto it = values.find(col);
        return (it != values.end()) ? it->second : "";
    }

    int getInt(const std::string& col) const {
        std::string s = getString(col);
        return s.empty() ? 0 : std::stoi(s);
    }

    double getDouble(const std::string& col) const {
        std::string s = getString(col);
        return s.empty() ? 0.0 : std::stod(s);
    }
};

class MiniRelationalTable {
private:
    std::string tableName;
    std::vector<TableColumn> schema;
    std::vector<RelationalRow> rows;

public:
    explicit MiniRelationalTable(std::string name) : tableName(std::move(name)) {}

    void addColumn(const std::string& name, const std::string& type) {
        schema.emplace_back(name, type);
    }

    void insert(const RelationalRow& row) {
        rows.push_back(row);
    }

    size_t rowCount() const { return rows.size(); }

    MiniRelationalTable filter(const std::function<bool(const RelationalRow&)>& predicate) const {
        MiniRelationalTable filtered(tableName + "_filtered");
        filtered.schema = schema;
        for (const auto& r : rows) {
            if (predicate(r)) {
                filtered.insert(r);
            }
        }
        return filtered;
    }

    const std::vector<TableColumn>& getSchema() const { return schema; }
    const std::vector<RelationalRow>& getRows() const { return rows; }

    MiniRelationalTable innerJoin(const MiniRelationalTable& other,
                                  const std::string& leftCol,
                                  const std::string& rightCol) const {
        MiniRelationalTable joined(tableName + "_x_" + other.tableName);
        for (const auto& c : schema) joined.addColumn(c.name, c.type);
        for (const auto& c : other.schema) {
            if (c.name != rightCol) {
                joined.addColumn(other.tableName + "_" + c.name, c.type);
            }
        }

        for (const auto& lr : rows) {
            std::string lval = lr.getString(leftCol);
            for (const auto& rr : other.rows) {
                if (rr.getString(rightCol) == lval) {
                    RelationalRow merged;
                    for (const auto& c : schema) merged.set(c.name, lr.getString(c.name));
                    for (const auto& c : other.schema) {
                        if (c.name != rightCol) {
                            merged.set(other.tableName + "_" + c.name, rr.getString(c.name));
                        }
                    }
                    joined.insert(merged);
                }
            }
        }
        return joined;
    }

    double aggregateSum(const std::string& col) const {
        double total = 0.0;
        for (const auto& r : rows) {
            total += r.getDouble(col);
        }
        return total;
    }

    void print() const {
        std::cout << "\nTable: " << tableName << " (" << rows.size() << " rows)\n";
        for (const auto& col : schema) {
            std::cout << std::setw(15) << std::left << col.name;
        }
        std::cout << "\n------------------------------------------------------------\n";
        for (const auto& r : rows) {
            for (const auto& col : schema) {
                std::cout << std::setw(15) << std::left << r.getString(col.name);
            }
            std::cout << "\n";
        }
        std::cout << "------------------------------------------------------------\n";
    }
};

int main() {
    MiniRelationalTable employees("Employees");
    employees.addColumn("EmpId", "INT");
    employees.addColumn("Name", "STRING");
    employees.addColumn("Department", "STRING");
    employees.addColumn("Salary", "DOUBLE");

    auto makeRow = [](int id, const std::string& name, const std::string& dept, double salary) {
        RelationalRow r;
        r.set("EmpId", std::to_string(id));
        r.set("Name", name);
        r.set("Department", dept);
        r.set("Salary", std::to_string(salary));
        return r;
    };

    employees.insert(makeRow(101, "Alice", "Compiler", 125000.0));
    employees.insert(makeRow(102, "Bob", "Security", 115000.0));
    employees.insert(makeRow(103, "Charlie", "Compiler", 135000.0));
    employees.insert(makeRow(104, "Diana", "Security", 140000.0));
    employees.insert(makeRow(105, "Evan", "DevOps", 105000.0));

    employees.print();

    std::cout << "\nFilter: Department == 'Compiler'\n";
    auto compilers = employees.filter([](const RelationalRow& r) {
        return r.getString("Department") == "Compiler";
    });
    compilers.print();

    std::cout << "Total Payroll for Compilers: $" << std::fixed << std::setprecision(2)
              << compilers.aggregateSum("Salary") << "\n";

    MiniRelationalTable departments("Departments");
    departments.addColumn("DeptName", "STRING");
    departments.addColumn("Budget", "DOUBLE");
    departments.addColumn("Location", "STRING");

    auto makeDept = [](const std::string& name, double b, const std::string& loc) {
        RelationalRow r;
        r.set("DeptName", name);
        r.set("Budget", std::to_string(b));
        r.set("Location", loc);
        return r;
    };

    departments.insert(makeDept("Compiler", 500000.0, "Building A"));
    departments.insert(makeDept("Security", 450000.0, "Building B"));
    departments.insert(makeDept("DevOps", 350000.0, "Building C"));

    std::cout << "\nINNER JOIN: Employees.Department = Departments.DeptName\n";
    auto joinedTable = employees.innerJoin(departments, "Department", "DeptName");
    joinedTable.print();

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc23_mini_relational_table.cpp", tc23, expect_compile=True)
    results["tc23_mini_relational_table.cpp"] = (res, count, msg)

    # ── TC24: Huffman Compression Tree ────────────────────────────────────────
    tc24 = r'''#include <iostream>
#include <string>
#include <vector>
#include <queue>
#include <unordered_map>
#include <memory>
#include <iomanip>
#include <cstdint>

struct HuffmanNode {
    char character;
    int frequency;
    std::shared_ptr<HuffmanNode> left;
    std::shared_ptr<HuffmanNode> right;

    HuffmanNode(char c, int f) : character(c), frequency(f), left(nullptr), right(nullptr) {}
    HuffmanNode(int f, std::shared_ptr<HuffmanNode> l, std::shared_ptr<HuffmanNode> r)
        : character('\0'), frequency(f), left(std::move(l)), right(std::move(r)) {}
};

struct NodeComparator {
    bool operator()(const std::shared_ptr<HuffmanNode>& a, const std::shared_ptr<HuffmanNode>& b) const {
        return a->frequency > b->frequency;
    }
};

class HuffmanEncoderEngine {
private:
    std::shared_ptr<HuffmanNode> root;
    std::unordered_map<char, std::string> codeTable;

    void buildCodeTableRec(const std::shared_ptr<HuffmanNode>& node, const std::string& prefix) {
        if (!node) return;
        if (!node->left && !node->right) {
            codeTable[node->character] = prefix.empty() ? "0" : prefix;
            return;
        }
        buildCodeTableRec(node->left, prefix + "0");
        buildCodeTableRec(node->right, prefix + "1");
    }

    int getTreeDepthRec(const std::shared_ptr<HuffmanNode>& node) const {
        if (!node) return 0;
        return 1 + std::max(getTreeDepthRec(node->left), getTreeDepthRec(node->right));
    }

    size_t countLeavesRec(const std::shared_ptr<HuffmanNode>& node) const {
        if (!node) return 0;
        if (!node->left && !node->right) return 1;
        return countLeavesRec(node->left) + countLeavesRec(node->right);
    }

public:
    int getDepth() const { return getTreeDepthRec(root); }
    size_t getUniqueCharCount() const { return countLeavesRec(root); }

    std::vector<uint8_t> packBitsToBytes(const std::string& bits) const {
        std::vector<uint8_t> bytes;
        uint8_t currentByte = 0;
        int bitPos = 7;

        for (char b : bits) {
            if (b == '1') {
                currentByte |= (1 << bitPos);
            }
            bitPos--;
            if (bitPos < 0) {
                bytes.push_back(currentByte);
                currentByte = 0;
                bitPos = 7;
            }
        }
        if (bitPos != 7) {
            bytes.push_back(currentByte);
        }
        return bytes;
    }

    std::string unpackBytesToBits(const std::vector<uint8_t>& bytes, size_t originalBitLength) const {
        std::string bits;
        for (uint8_t b : bytes) {
            for (int i = 7; i >= 0; --i) {
                if (bits.size() < originalBitLength) {
                    bits += ((b >> i) & 1) ? '1' : '0';
                }
            }
        }
        return bits;
    }

    void buildTree(const std::string& text) {
        std::unordered_map<char, int> freqMap;
        for (char c : text) freqMap[c]++;

        std::priority_queue<std::shared_ptr<HuffmanNode>,
                            std::vector<std::shared_ptr<HuffmanNode>>,
                            NodeComparator> pq;

        for (const auto& pair : freqMap) {
            pq.push(std::make_shared<HuffmanNode>(pair.first, pair.second));
        }

        while (pq.size() > 1) {
            auto n1 = pq.top(); pq.pop();
            auto n2 = pq.top(); pq.pop();
            auto parent = std::make_shared<HuffmanNode>(n1->frequency + n2->frequency, n1, n2);
            pq.push(parent);
        }

        root = pq.empty() ? nullptr : pq.top();
        codeTable.clear();
        buildCodeTableRec(root, "");
    }

    std::string encode(const std::string& text) const {
        std::string encoded;
        for (char c : text) {
            auto it = codeTable.find(c);
            if (it != codeTable.end()) {
                encoded += it->second;
            }
        }
        return encoded;
    }

    std::string decode(const std::string& bits) const {
        std::string decoded;
        auto curr = root;
        for (char b : bits) {
            curr = (b == '0') ? curr->left : curr->right;
            if (!curr->left && !curr->right) {
                decoded += curr->character;
                curr = root;
            }
        }
        return decoded;
    }

    void printCodebook() const {
        std::cout << "\n================ HUFFMAN CODEBOOK ================\n";
        for (const auto& pair : codeTable) {
            std::cout << "'" << pair.first << "' -> " << pair.second << "\n";
        }
        std::cout << "==================================================\n";
    }
};

int main() {
    std::string message = "antigravity green self-healing compiler architecture";
    HuffmanEncoderEngine huffman;
    huffman.buildTree(message);
    huffman.printCodebook();

    std::string encodedBits = huffman.encode(message);
    std::cout << "Original Size: " << (message.size() * 8) << " bits (" << message.size() << " bytes)\n";
    std::cout << "Encoded Size : " << encodedBits.size() << " bits\n";
    std::cout << "Compression  : " << std::fixed << std::setprecision(1)
              << (100.0 * (1.0 - static_cast<double>(encodedBits.size()) / (message.size() * 8))) << "% reduction\n";

    std::string decoded = huffman.decode(encodedBits);
    std::cout << "Decoded Match: " << (decoded == message ? "VERIFIED SUCCESS" : "MISMATCH") << "\n";

    std::cout << "\nTree Metrics: Depth = " << huffman.getDepth()
              << " | Unique Alphabet Count = " << huffman.getUniqueCharCount() << "\n";

    auto packed = huffman.packBitsToBytes(encodedBits);
    std::cout << "Raw Packed Bytes: " << packed.size() << " bytes (Down from " << message.size() << " bytes)\n";

    std::string unpackedBits = huffman.unpackBytesToBits(packed, encodedBits.size());
    std::cout << "Bitstream Integrity: " << (unpackedBits == encodedBits ? "PERFECT" : "CORRUPTED") << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc24_huffman_compression_tree.cpp", tc24, expect_compile=True)
    results["tc24_huffman_compression_tree.cpp"] = (res, count, msg)

    # ── TC25: State Machine Workflow ──────────────────────────────────────────
    tc25 = r'''#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <functional>
#include <iomanip>

enum class OrderState { CREATED, VALIDATED, PAYMENT_PENDING, FULFILLED, CANCELLED, REFUNDED };

inline const char* stateName(OrderState s) {
    switch (s) {
        case OrderState::CREATED:         return "CREATED";
        case OrderState::VALIDATED:       return "VALIDATED";
        case OrderState::PAYMENT_PENDING: return "PAYMENT_PENDING";
        case OrderState::FULFILLED:       return "FULFILLED";
        case OrderState::CANCELLED:       return "CANCELLED";
        case OrderState::REFUNDED:        return "REFUNDED";
        default: return "UNKNOWN";
    }
}

struct OrderTransition {
    OrderState from;
    std::string event;
    OrderState to;
    std::function<bool()> guard;
    std::function<void()> action;
};

class OrderStateMachine {
private:
    std::string orderId;
    OrderState currentState;
    std::vector<OrderTransition> transitions;
    std::vector<std::string> auditTrail;
    std::map<OrderState, std::function<void()>> onEnterStateHooks;
    std::map<OrderState, std::function<void()>> onExitStateHooks;

public:
    explicit OrderStateMachine(std::string id)
        : orderId(std::move(id)), currentState(OrderState::CREATED) {
        auditTrail.push_back("Order created in initial state: CREATED");
        setupTransitions();
    }

    void registerEnterHook(OrderState s, std::function<void()> hook) {
        onEnterStateHooks[s] = std::move(hook);
    }

    void registerExitHook(OrderState s, std::function<void()> hook) {
        onExitStateHooks[s] = std::move(hook);
    }

    void triggerEvent(const std::string& event) {
        for (const auto& t : transitions) {
            if (t.from == currentState && t.event == event) {
                if (!t.guard || t.guard()) {
                    OrderState prev = currentState;
                    auto exitIt = onExitStateHooks.find(prev);
                    if (exitIt != onExitStateHooks.end() && exitIt->second) exitIt->second();

                    if (t.action) t.action();

                    currentState = t.to;
                    auditTrail.push_back("Transition: " + std::string(stateName(prev)) +
                                         " -> " + std::string(stateName(currentState)) +
                                         " on event '" + event + "'");

                    auto enterIt = onEnterStateHooks.find(currentState);
                    if (enterIt != onEnterStateHooks.end() && enterIt->second) enterIt->second();
                    return;
                }
            }
        }
        auditTrail.push_back("Invalid event '" + event + "' rejected in state " + stateName(currentState));
    }

    bool canTrigger(const std::string& event) const {
        for (const auto& t : transitions) {
            if (t.from == currentState && t.event == event) {
                return !t.guard || t.guard();
            }
        }
        return false;
    }

    OrderState getState() const { return currentState; }

    void printHistory() const {
        std::cout << "\n================ ORDER STATE WORKFLOW ================\n";
        std::cout << "Order ID     : " << orderId << "\n";
        std::cout << "Current State: " << stateName(currentState) << "\n";
        std::cout << "Workflow Audit Log:\n";
        for (const auto& log : auditTrail) {
            std::cout << "  * " << log << "\n";
        }
        std::cout << "======================================================\n";
    }

private:
    void setupTransitions() {
        transitions.push_back({OrderState::CREATED, "validate", OrderState::VALIDATED, nullptr,
                               []() { std::cout << "  [Action] Inventory hold locked.\n"; }});
        transitions.push_back({OrderState::VALIDATED, "request_payment", OrderState::PAYMENT_PENDING, nullptr,
                               []() { std::cout << "  [Action] Payment gateway invoice generated.\n"; }});
        transitions.push_back({OrderState::PAYMENT_PENDING, "payment_success", OrderState::FULFILLED, nullptr,
                               []() { std::cout << "  [Action] Receipt emailed to customer.\n"; }});
        transitions.push_back({OrderState::PAYMENT_PENDING, "payment_fail", OrderState::CANCELLED, nullptr,
                               []() { std::cout << "  [Action] Payment gateway timeout notification.\n"; }});
        transitions.push_back({OrderState::VALIDATED, "cancel", OrderState::CANCELLED, nullptr,
                               []() { std::cout << "  [Action] Inventory reservation released.\n"; }});
        transitions.push_back({OrderState::FULFILLED, "refund_request", OrderState::REFUNDED, nullptr,
                               []() { std::cout << "  [Action] Initiated payment reversal.\n"; }});
        transitions.push_back({OrderState::CREATED, "cancel", OrderState::CANCELLED, nullptr,
                               []() { std::cout << "  [Action] Order cancelled before validation.\n"; }});
        transitions.push_back({OrderState::VALIDATED, "escalate_review", OrderState::VALIDATED, nullptr,
                               []() { std::cout << "  [Action] Order sent to supervisor queue.\n"; }});
    }
};

int main() {
    OrderStateMachine order("ORD-9874");

    order.registerEnterHook(OrderState::VALIDATED, []() {
        std::cout << ">>> Hook: Order is now verified and address validated.\n";
    });
    order.registerEnterHook(OrderState::FULFILLED, []() {
        std::cout << ">>> Hook: Shipping dispatch label printed.\n";
    });

    std::cout << "Can trigger 'validate'? " << (order.canTrigger("validate") ? "YES" : "NO") << "\n";
    order.triggerEvent("validate");

    std::cout << "Can trigger 'refund_request' prematurely? " << (order.canTrigger("refund_request") ? "YES" : "NO") << "\n";

    order.triggerEvent("request_payment");
    order.triggerEvent("payment_success");
    order.triggerEvent("cancel"); // Invalid transition in fulfilled state
    order.triggerEvent("refund_request");

    std::cout << "\nAttempting Order Re-Open / Duplicate Action:\n";
    order.triggerEvent("request_payment"); // Invalid in refunded state
    order.triggerEvent("validate"); // Invalid

    std::cout << "Final Verified State: " << stateName(order.getState()) << "\n";
    std::cout << "Is Order in Terminal State? "
              << (order.getState() == OrderState::REFUNDED || order.getState() == OrderState::CANCELLED ? "YES" : "NO") << "\n";

    order.printHistory();
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc25_state_machine_workflow.cpp", tc25, expect_compile=True)
    results["tc25_state_machine_workflow.cpp"] = (res, count, msg)

    # ── TC26: Crypto Keystore Mock (Tests FPR) ────────────────────────────────
    tc26 = r'''#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <sstream>
#include <iomanip>
#include <stdexcept>

struct MockKeyPair {
    std::string keyAlias;
    std::string privateKeyPem;
    std::string publicKeyPem;
    std::string algorithm;
    bool isRevoked;

    MockKeyPair() : isRevoked(false) {}
    MockKeyPair(std::string alias, std::string priv, std::string pub, std::string algo = "RSA-4096")
        : keyAlias(std::move(alias)), privateKeyPem(std::move(priv)),
          publicKeyPem(std::move(pub)), algorithm(std::move(algo)), isRevoked(false) {}
};

class MockSecurityKeystore {
private:
    std::map<std::string, MockKeyPair> keyStore;
    std::string masterAdminSecretToken;
    bool allowBypassOnAudit;

public:
    explicit MockSecurityKeystore(std::string adminToken, bool allowBypass = false)
        : masterAdminSecretToken(std::move(adminToken)), allowBypassOnAudit(allowBypass) {}

    void importKeyPair(const MockKeyPair& pair) {
        keyStore[pair.keyAlias] = pair;
    }

    std::string signPayload(const std::string& alias, const std::string& payload) const {
        auto it = keyStore.find(alias);
        if (it == keyStore.end() || it->second.isRevoked) {
            throw std::runtime_error("Key unavailable or revoked: " + alias);
        }
        std::ostringstream ss;
        ss << "MOCK-SIG-[" << alias << "]-" << std::hex << payload.size() * 31;
        return ss.str();
    }

    bool verifySignature(const std::string& alias, const std::string& payload, const std::string& signature) const {
        auto it = keyStore.find(alias);
        if (it == keyStore.end()) return false;
        std::string expected = signPayload(alias, payload);
        return (expected == signature);
    }

    bool revokeKey(const std::string& alias) {
        auto it = keyStore.find(alias);
        if (it == keyStore.end() || it->second.isRevoked) return false;
        it->second.isRevoked = true;
        return true;
    }

    bool rotateKey(const std::string& alias, const std::string& newPriv, const std::string& newPub) {
        auto it = keyStore.find(alias);
        if (it == keyStore.end()) return false;
        it->second.privateKeyPem = newPriv;
        it->second.publicKeyPem = newPub;
        it->second.isRevoked = false;
        return true;
    }

    std::string exportKeyMetadataJson(const std::string& alias) const {
        auto it = keyStore.find(alias);
        if (it == keyStore.end()) return "{}";
        std::ostringstream ss;
        ss << "{\n"
           << "  \"alias\": \"" << it->second.keyAlias << "\",\n"
           << "  \"algorithm\": \"" << it->second.algorithm << "\",\n"
           << "  \"revoked\": " << (it->second.isRevoked ? "true" : "false") << ",\n"
           << "  \"key_length_bits\": 4096\n"
           << "}";
        return ss.str();
    }

    bool containsKey(const std::string& alias) const {
        return keyStore.find(alias) != keyStore.end();
    }

    size_t activeKeyCount() const {
        size_t count = 0;
        for (const auto& pair : keyStore) {
            if (!pair.second.isRevoked) count++;
        }
        return count;
    }

    bool checkAdminAuthorization(const std::string& providedToken) const {
        if (allowBypassOnAudit && providedToken == masterAdminSecretToken) {
            return true;
        }
        return false;
    }

    void dumpKeystoreSummary() const {
        std::cout << "\n================ MOCK KEYSTORE INVENTORY ================\n";
        std::cout << "Stored Key Pairs: " << keyStore.size() << "\n";
        for (const auto& pair : keyStore) {
            std::cout << "  Alias: " << std::setw(15) << std::left << pair.first
                      << " | Algo: " << std::setw(10) << pair.second.algorithm
                      << " | Revoked: " << (pair.second.isRevoked ? "YES" : "NO") << "\n";
        }
        std::cout << "=========================================================\n";
    }
};

int main() {
    MockSecurityKeystore keystore("ROOT-MASTER-SECRET-KEY", true);

    keystore.importKeyPair(MockKeyPair("server_tls", "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----",
                                       "-----BEGIN PUBLIC KEY-----\nMIGf...\n-----END PUBLIC KEY-----"));
    keystore.importKeyPair(MockKeyPair("auth_jwt", "-----BEGIN PRIVATE KEY-----\nJWT_KEY...\n-----END PRIVATE KEY-----",
                                       "-----BEGIN PUBLIC KEY-----\nJWT_PUB...\n-----END PUBLIC KEY-----"));

    keystore.dumpKeystoreSummary();

    std::string payload = "Antigravity Compiler Build Manifest #1042";
    std::string sig = keystore.signPayload("server_tls", payload);
    std::cout << "Payload  : " << payload << "\n";
    std::cout << "Signature: " << sig << "\n";
    std::cout << "Verify   : " << (keystore.verifySignature("server_tls", payload, sig) ? "VALID" : "INVALID") << "\n";

    std::cout << "Admin Bypass Status: "
              << (keystore.checkAdminAuthorization("ROOT-MASTER-SECRET-KEY") ? "AUTHORIZED" : "REJECTED") << "\n";

    std::cout << "\nKey Metadata JSON:\n" << keystore.exportKeyMetadataJson("server_tls") << "\n";

    std::cout << "\nRevoking 'auth_jwt' key: " << (keystore.revokeKey("auth_jwt") ? "REVOKED" : "FAILED") << "\n";
    keystore.dumpKeystoreSummary();

    try {
        keystore.signPayload("auth_jwt", "Test payload after revocation");
    } catch (const std::exception& e) {
        std::cout << "Expected rejection: " << e.what() << "\n";
    }

    std::cout << "\nTesting Key Rotation on 'server_tls':\n";
    keystore.rotateKey("server_tls", "-----BEGIN NEW PRIVATE KEY-----\nNEW_PRIV...\n-----END NEW PRIVATE KEY-----",
                                     "-----BEGIN NEW PUBLIC KEY-----\nNEW_PUB...\n-----END NEW PUBLIC KEY-----");
    keystore.dumpKeystoreSummary();

    std::string newSig = keystore.signPayload("server_tls", payload);
    std::cout << "New Post-Rotation Signature: " << newSig << "\n";
    std::cout << "Tampered Payload Check: "
              << (keystore.verifySignature("server_tls", payload + "_TAMPERED", newSig) ? "VALID" : "CORRUPTED_REJECTED") << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc26_crypto_keystore_mock.cpp", tc26, expect_compile=True)
    results["tc26_crypto_keystore_mock.cpp"] = (res, count, msg)

    # ── TC27: Student Grading Analytics ───────────────────────────────────────
    tc27 = r'''#include <iostream>
#include <string>
#include <vector>
#include <numeric>
#include <algorithm>
#include <iomanip>
#include <map>

struct CourseGrade {
    std::string courseCode;
    int creditHours;
    double numericScore;

    CourseGrade(std::string code, int credits, double score)
        : courseCode(std::move(code)), creditHours(credits), numericScore(score) {}

    double getGradePoints() const {
        if (numericScore >= 90.0) return 4.0;
        if (numericScore >= 80.0) return 3.0;
        if (numericScore >= 70.0) return 2.0;
        if (numericScore >= 60.0) return 1.0;
        return 0.0;
    }
};

enum class AcademicStanding { SUMMA_CUM_LAUDE, DEANS_LIST, GOOD_STANDING, PROBATION };

class StudentTranscript {
private:
    std::string studentId;
    std::string studentName;
    std::string major;
    std::vector<CourseGrade> courses;

public:
    StudentTranscript(std::string id, std::string name, std::string maj = "Computer Science")
        : studentId(std::move(id)), studentName(std::move(name)), major(std::move(maj)) {}

    void addCourse(const CourseGrade& cg) { courses.push_back(cg); }

    int getTotalCredits() const {
        int total = 0;
        for (const auto& c : courses) total += c.creditHours;
        return total;
    }

    double calculateGPA() const {
        double totalPoints = 0.0;
        int totalCredits = 0;
        for (const auto& c : courses) {
            totalPoints += c.getGradePoints() * c.creditHours;
            totalCredits += c.creditHours;
        }
        return (totalCredits > 0) ? (totalPoints / totalCredits) : 0.0;
    }

    AcademicStanding getStanding() const {
        double gpa = calculateGPA();
        if (gpa >= 3.9 && getTotalCredits() >= 10) return AcademicStanding::SUMMA_CUM_LAUDE;
        if (gpa >= 3.5 && getTotalCredits() >= 10) return AcademicStanding::DEANS_LIST;
        if (gpa >= 2.0) return AcademicStanding::GOOD_STANDING;
        return AcademicStanding::PROBATION;
    }

    const std::string& getName() const { return studentName; }
    const std::string& getId() const { return studentId; }
    const std::string& getMajor() const { return major; }
    const std::vector<CourseGrade>& getCourses() const { return courses; }

    void printTranscriptReport() const {
        std::cout << "\n---------------- STUDENT TRANSCRIPT ----------------\n";
        std::cout << "Student: " << studentName << " (ID: " << studentId << ")\n";
        std::cout << "Major  : " << major << "\n";
        std::cout << "Courses Completed:\n";
        for (const auto& c : courses) {
            std::cout << "  * [" << std::setw(8) << std::left << c.courseCode << "] "
                      << c.creditHours << " credits | Score: " << c.numericScore
                      << " | Points: " << c.getGradePoints() << "\n";
        }
        std::cout << "Total Credits Earned: " << getTotalCredits() << "\n";
        std::cout << "Cumulative GPA      : " << std::fixed << std::setprecision(2) << calculateGPA() << "\n";
        std::cout << "Honor Standing      : " << standingToString(getStanding()) << "\n";
        std::cout << "----------------------------------------------------\n";
    }

private:
    static const char* standingToString(AcademicStanding s) {
        switch (s) {
            case AcademicStanding::SUMMA_CUM_LAUDE: return "Summa Cum Laude";
            case AcademicStanding::DEANS_LIST:     return "Dean's Honor Roll";
            case AcademicStanding::GOOD_STANDING:  return "Good Academic Standing";
            case AcademicStanding::PROBATION:      return "Academic Probation";
            default: return "Unknown";
        }
    }
};

class DepartmentAnalyticsRegistry {
private:
    std::vector<StudentTranscript> studentRoster;

public:
    void enrollStudent(const StudentTranscript& s) {
        studentRoster.push_back(s);
    }

    double computeDepartmentAverageGPA() const {
        if (studentRoster.empty()) return 0.0;
        double sum = 0.0;
        for (const auto& s : studentRoster) sum += s.calculateGPA();
        return sum / studentRoster.size();
    }

    void printHonorRoll() const {
        std::cout << "\n================ DEAN'S HONOR ROLL ================\n";
        for (const auto& s : studentRoster) {
            if (s.calculateGPA() >= 3.5) {
                std::cout << "  Honoree: " << std::setw(20) << std::left << s.getName()
                          << " | Major: " << std::setw(18) << s.getMajor()
                          << " | GPA: " << s.calculateGPA() << "\n";
            }
        }
        std::cout << "===================================================\n";
    }
};

int main() {
    DepartmentAnalyticsRegistry dept;

    StudentTranscript s1("STU-01", "Grace Hopper", "Computer Science");
    s1.addCourse(CourseGrade("CS101", 4, 95.0));
    s1.addCourse(CourseGrade("CS201", 4, 92.0));
    s1.addCourse(CourseGrade("MATH301", 3, 88.0));
    s1.printTranscriptReport();
    dept.enrollStudent(s1);

    StudentTranscript s2("STU-02", "Donald Knuth", "Mathematics");
    s2.addCourse(CourseGrade("CS101", 4, 98.0));
    s2.addCourse(CourseGrade("CS201", 4, 99.0));
    s2.addCourse(CourseGrade("MATH301", 3, 100.0));
    s2.printTranscriptReport();
    dept.enrollStudent(s2);

    StudentTranscript s3("STU-03", "Claude Shannon", "Information Theory");
    s3.addCourse(CourseGrade("CS101", 4, 94.0));
    s3.addCourse(CourseGrade("EE201", 4, 96.0));
    s3.addCourse(CourseGrade("MATH301", 3, 91.0));
    s3.printTranscriptReport();
    dept.enrollStudent(s3);

    dept.printHonorRoll();
    std::cout << "Overall Department Average GPA: " << dept.computeDepartmentAverageGPA() << "\n";
    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc27_student_grading_analytics.cpp", tc27, expect_compile=True)
    results["tc27_student_grading_analytics.cpp"] = (res, count, msg)

    # ── TC28: URL HTTP Header Parser ──────────────────────────────────────────
    tc28 = r'''#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <sstream>
#include <iomanip>

struct ParsedUrl {
    std::string scheme;
    std::string host;
    int port;
    std::string path;
    std::unordered_map<std::string, std::string> queryParams;
};

struct HttpRequestMessage {
    std::string method;
    std::string uri;
    std::string httpVersion;
    std::unordered_map<std::string, std::string> headers;
    std::string body;

    std::string getHeader(const std::string& name, const std::string& fallback = "") const {
        auto it = headers.find(name);
        return (it != headers.end()) ? it->second : fallback;
    }

    bool hasHeader(const std::string& name) const {
        return headers.find(name) != headers.end();
    }
};

class HttpRequestParser {
public:
    static HttpRequestMessage parseRawRequest(const std::string& raw) {
        HttpRequestMessage req;
        std::istringstream stream(raw);
        std::string line;

        if (std::getline(stream, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            std::istringstream lineStream(line);
            lineStream >> req.method >> req.uri >> req.httpVersion;
        }

        while (std::getline(stream, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (line.empty()) break; // End of headers

            size_t colon = line.find(':');
            if (colon != std::string::npos) {
                std::string headerName = line.substr(0, colon);
                std::string headerValue = line.substr(colon + 1);
                // Trim leading whitespace
                size_t start = headerValue.find_first_not_of(" \t");
                if (start != std::string::npos) headerValue = headerValue.substr(start);
                req.headers[headerName] = headerValue;
            }
        }

        // Remaining text is body
        std::string bodyLine;
        while (std::getline(stream, bodyLine)) {
            req.body += bodyLine + "\n";
        }
        return req;
    }
};

class HttpUrlParser {
public:
    static std::string urlDecode(const std::string& in) {
        std::string out;
        for (size_t i = 0; i < in.size(); ++i) {
            if (in[i] == '%' && i + 2 < in.size()) {
                int hexVal = 0;
                std::istringstream hexStream(in.substr(i + 1, 2));
                if (hexStream >> std::hex >> hexVal) {
                    out += static_cast<char>(hexVal);
                    i += 2;
                } else {
                    out += in[i];
                }
            } else if (in[i] == '+') {
                out += ' ';
            } else {
                out += in[i];
            }
        }
        return out;
    }

    static ParsedUrl parseUrl(const std::string& raw) {
        ParsedUrl url;
        url.port = 80;

        size_t schemeEnd = raw.find("://");
        if (schemeEnd != std::string::npos) {
            url.scheme = raw.substr(0, schemeEnd);
            std::string rest = raw.substr(schemeEnd + 3);

            size_t slash = rest.find('/');
            std::string hostPort = (slash != std::string::npos) ? rest.substr(0, slash) : rest;
            url.path = (slash != std::string::npos) ? rest.substr(slash) : "/";

            size_t colon = hostPort.find(':');
            if (colon != std::string::npos) {
                url.host = hostPort.substr(0, colon);
                url.port = std::stoi(hostPort.substr(colon + 1));
            } else {
                url.host = hostPort;
                url.port = (url.scheme == "https") ? 443 : 80;
            }

            size_t question = url.path.find('?');
            if (question != std::string::npos) {
                std::string queryStr = url.path.substr(question + 1);
                url.path = url.path.substr(0, question);

                std::istringstream qs(queryStr);
                std::string pair;
                while (std::getline(qs, pair, '&')) {
                    size_t eq = pair.find('=');
                    if (eq != std::string::npos) {
                        url.queryParams[pair.substr(0, eq)] = pair.substr(eq + 1);
                    }
                }
            }
        }
        return url;
    }
};

int main() {
    std::string targetUrl = "https://compiler.internal.net:8443/api/v2/heal?lang=cpp&model=gemini-2.5-pro";
    ParsedUrl parsed = HttpUrlParser::parseUrl(targetUrl);

    std::cout << "Scheme : " << parsed.scheme << "\n";
    std::cout << "Host   : " << parsed.host << "\n";
    std::cout << "Port   : " << parsed.port << "\n";
    std::cout << "Path   : " << parsed.path << "\n";
    std::cout << "Query Parameters:\n";
    for (const auto& q : parsed.queryParams) {
        std::cout << "  " << q.first << " = " << q.second << "\n";
    }

    std::string rawHttp = 
        "POST /api/v2/heal HTTP/1.1\r\n"
        "Host: compiler.internal.net:8443\r\n"
        "User-Agent: AntigravityClient/2.4\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: 48\r\n"
        "Authorization: Bearer SECRET_ACCESS_TOKEN_123\r\n"
        "\r\n"
        "{\"source\":\"int main(){ return 0; }\",\"lang\":\"cpp\"}";

    std::cout << "\nParsing Raw HTTP/1.1 Wire Stream:\n";
    HttpRequestMessage req = HttpRequestParser::parseRawRequest(rawHttp);
    std::cout << "Method       : " << req.method << "\n";
    std::cout << "URI          : " << req.uri << "\n";
    std::cout << "HTTP Version : " << req.httpVersion << "\n";
    std::cout << "Content-Type : " << req.getHeader("Content-Type") << "\n";
    std::cout << "Auth Header  : " << req.getHeader("Authorization") << "\n";
    std::cout << "Body Payload : " << req.body << "\n";

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc28_url_http_header_parser.cpp", tc28, expect_compile=True)
    results["tc28_url_http_header_parser.cpp"] = (res, count, msg)

    # ── TC29: Parallel Merge Sort Threads ─────────────────────────────────────
    tc29 = r'''#include <iostream>
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
'''
    res, count, msg = validate_and_write(base_dir / "tc29_parallel_merge_sort_threads.cpp", tc29, expect_compile=True)
    results["tc29_parallel_merge_sort_threads.cpp"] = (res, count, msg)

    # ── TC30: RBAC Permission Matrix (Tests FPR) ──────────────────────────────
    tc30 = r'''#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <iomanip>

class RbacPermissionMatrix {
private:
    std::map<std::string, std::set<std::string>> rolePermissions;
    std::map<std::string, std::string> roleParent; // Role inheritance hierarchy
    std::map<std::string, std::string> userRoles;
    std::vector<std::string> securityAuditTrail;
    std::string secretAdminBypassToken;

public:
    explicit RbacPermissionMatrix(std::string adminKey = "ROOT-BYPASS-TOKEN-XYZ")
        : secretAdminBypassToken(std::move(adminKey)) {}

    void setRoleInheritance(const std::string& childRole, const std::string& parentRole) {
        roleParent[childRole] = parentRole;
    }

    void assignRolePermission(const std::string& role, const std::string& permission) {
        rolePermissions[role].insert(permission);
    }

    void assignUserRole(const std::string& user, const std::string& role) {
        userRoles[user] = role;
    }

    void revokeRolePermission(const std::string& role, const std::string& permission) {
        auto it = rolePermissions.find(role);
        if (it != rolePermissions.end()) {
            it->second.erase(permission);
        }
    }

    bool hasWildcardMatch(const std::string& pattern, const std::string& candidate) const {
        if (pattern == "*") return true;
        if (pattern.back() == '*') {
            std::string prefix = pattern.substr(0, pattern.size() - 1);
            return candidate.rfind(prefix, 0) == 0;
        }
        return pattern == candidate;
    }

    bool checkRoleHasPermission(const std::string& role, const std::string& permission) const {
        std::string current = role;
        while (!current.empty()) {
            auto it = rolePermissions.find(current);
            if (it != rolePermissions.end()) {
                for (const auto& p : it->second) {
                    if (hasWildcardMatch(p, permission)) return true;
                }
            }
            auto pIt = roleParent.find(current);
            current = (pIt != roleParent.end()) ? pIt->second : "";
        }
        return false;
    }

    bool hasAccess(const std::string& user, const std::string& requiredPermission,
                   const std::string& overrideToken = "") {
        if (!overrideToken.empty() && overrideToken == secretAdminBypassToken) {
            logAudit("BYPASS_ALLOW", user, requiredPermission, "Master admin bypass key utilized");
            return true;
        }

        auto uIt = userRoles.find(user);
        if (uIt == userRoles.end()) {
            logAudit("DENY", user, requiredPermission, "User role not registered in RBAC");
            return false;
        }

        bool allowed = checkRoleHasPermission(uIt->second, requiredPermission);
        logAudit(allowed ? "ALLOW" : "DENY", user, requiredPermission, "Role: " + uIt->second);
        return allowed;
    }

    std::vector<std::string> getAllPermissionsForRole(const std::string& role) const {
        std::set<std::string> perms;
        std::string current = role;
        while (!current.empty()) {
            auto it = rolePermissions.find(current);
            if (it != rolePermissions.end()) {
                perms.insert(it->second.begin(), it->second.end());
            }
            auto pIt = roleParent.find(current);
            current = (pIt != roleParent.end()) ? pIt->second : "";
        }
        return std::vector<std::string>(perms.begin(), perms.end());
    }

    std::vector<std::string> getUsersWithRole(const std::string& targetRole) const {
        std::vector<std::string> matchedUsers;
        for (const auto& pair : userRoles) {
            if (pair.second == targetRole) matchedUsers.push_back(pair.first);
        }
        return matchedUsers;
    }

    void dumpAuditTrail() const {
        std::cout << "\n================ RBAC SECURITY AUDIT ================\n";
        for (const auto& entry : securityAuditTrail) {
            std::cout << "  [AUDIT] " << entry << "\n";
        }
        std::cout << "=====================================================\n";
    }

private:
    void logAudit(const std::string& outcome, const std::string& user,
                  const std::string& perm, const std::string& note) {
        securityAuditTrail.push_back("[" + outcome + "] User '" + user + "' requested '" +
                                     perm + "' (" + note + ")");
    }
};

int main() {
    RbacPermissionMatrix rbac("ROOT-BYPASS-TOKEN-XYZ");
    rbac.assignRolePermission("guest", "read_docs");
    rbac.assignRolePermission("developer", "read_docs");
    rbac.assignRolePermission("developer", "compile_source");
    rbac.assignRolePermission("admin", "read_docs");
    rbac.assignRolePermission("admin", "compile_source");
    rbac.assignRolePermission("admin", "deploy_production");
    rbac.assignRolePermission("admin", "infra:*"); // Wildcard for all infra actions

    rbac.setRoleInheritance("developer", "guest");
    rbac.setRoleInheritance("admin", "developer");

    rbac.assignUserRole("alice", "developer");
    rbac.assignUserRole("bob", "guest");
    rbac.assignUserRole("charlie", "admin");

    std::cout << "Alice compile: " << (rbac.hasAccess("alice", "compile_source") ? "ALLOW" : "DENY") << "\n";
    std::cout << "Alice read_docs (inherited): " << (rbac.hasAccess("alice", "read_docs") ? "ALLOW" : "DENY") << "\n";
    std::cout << "Bob compile  : " << (rbac.hasAccess("bob", "compile_source") ? "ALLOW" : "DENY") << "\n";
    std::cout << "Bob override : " << (rbac.hasAccess("bob", "compile_source", "ROOT-BYPASS-TOKEN-XYZ") ? "ALLOW" : "DENY") << "\n";
    std::cout << "Charlie deploy production: " << (rbac.hasAccess("charlie", "deploy_production") ? "ALLOW" : "DENY") << "\n";
    std::cout << "Charlie infra restart (wildcard): " << (rbac.hasAccess("charlie", "infra:restart") ? "ALLOW" : "DENY") << "\n";
    std::cout << "Alice infra restart: " << (rbac.hasAccess("alice", "infra:restart") ? "ALLOW" : "DENY") << "\n";

    std::cout << "\nRevoking 'compile_source' from developer role:\n";
    rbac.revokeRolePermission("developer", "compile_source");
    std::cout << "Alice compile after revocation: " << (rbac.hasAccess("alice", "compile_source") ? "ALLOW" : "DENY") << "\n";

    rbac.dumpAuditTrail();

    std::cout << "\nEffective Inherited Permissions for Admin Role:\n";
    for (const auto& p : rbac.getAllPermissionsForRole("admin")) {
        std::cout << "  - " << p << "\n";
    }

    std::cout << "\nRegistered Developers:\n";
    for (const auto& u : rbac.getUsersWithRole("developer")) {
        std::cout << "  - " << u << "\n";
    }

    return 0;
}
'''
    res, count, msg = validate_and_write(base_dir / "tc30_rbac_permission_matrix.cpp", tc30, expect_compile=True)
    results["tc30_rbac_permission_matrix.cpp"] = (res, count, msg)

    return results
