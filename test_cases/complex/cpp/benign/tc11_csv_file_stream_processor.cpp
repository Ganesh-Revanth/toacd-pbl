#include <iostream>
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
