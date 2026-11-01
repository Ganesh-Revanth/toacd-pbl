#include <iostream>
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
