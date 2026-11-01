#include <iostream>
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
