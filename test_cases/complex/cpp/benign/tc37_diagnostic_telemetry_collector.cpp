#include <iostream>
#include <string>
#include <vector>
#include <numeric>
#include <algorithm>
#include <iomanip>
#include <cmath>

struct DiagnosticSample {
    std::string metricName;
    double value;
    std::string timestamp;

    DiagnosticSample(std::string name, double v, std::string ts)
        : metricName(std::move(name)), value(v), timestamp(std::move(ts)) {}
};

class TelemetryCollectorEngine {
private:
    std::vector<DiagnosticSample> samples;

public:
    void record(const std::string& metric, double val) {
        samples.emplace_back(metric, val, "2026-11-01 14:00:00");
    }

    std::vector<double> getValues(const std::string& metric) const {
        std::vector<double> vals;
        for (const auto& s : samples) {
            if (s.metricName == metric) vals.push_back(s.value);
        }
        std::sort(vals.begin(), vals.end());
        return vals;
    }

    double computePercentile(const std::string& metric, double p) const {
        auto vals = getValues(metric);
        if (vals.empty()) return 0.0;
        size_t idx = static_cast<size_t>(std::ceil(p * vals.size())) - 1;
        if (idx >= vals.size()) idx = vals.size() - 1;
        return vals[idx];
    }

    double computeMean(const std::string& metric) const {
        auto vals = getValues(metric);
        if (vals.empty()) return 0.0;
        double sum = std::accumulate(vals.begin(), vals.end(), 0.0);
        return sum / vals.size();
    }

    double computeStdDev(const std::string& metric) const {
        auto vals = getValues(metric);
        if (vals.size() < 2) return 0.0;
        double mean = computeMean(metric);
        double sqSum = 0.0;
        for (double v : vals) {
            double diff = v - mean;
            sqSum += diff * diff;
        }
        return std::sqrt(sqSum / (vals.size() - 1));
    }

    double computeMin(const std::string& metric) const {
        auto vals = getValues(metric);
        return vals.empty() ? 0.0 : vals.front();
    }

    double computeMax(const std::string& metric) const {
        auto vals = getValues(metric);
        return vals.empty() ? 0.0 : vals.back();
    }

    std::vector<DiagnosticSample> detectAnomalies(const std::string& metric, double sigmaThreshold = 3.0) const {
        std::vector<DiagnosticSample> anomalies;
        double mean = computeMean(metric);
        double stddev = computeStdDev(metric);
        if (stddev < 1e-6) return anomalies;

        for (const auto& s : samples) {
            if (s.metricName == metric && std::abs(s.value - mean) > (sigmaThreshold * stddev)) {
                anomalies.push_back(s);
            }
        }
        return anomalies;
    }

    std::vector<std::string> getDistinctMetricNames() const {
        std::vector<std::string> names;
        for (const auto& s : samples) {
            if (std::find(names.begin(), names.end(), s.metricName) == names.end()) {
                names.push_back(s.metricName);
            }
        }
        return names;
    }

    void clear() {
        samples.clear();
    }

    size_t totalSampleCount() const {
        return samples.size();
    }

    void printGlobalDashboard() const {
        std::cout << "\n================ GLOBAL TELEMETRY DASHBOARD ================\n";
        auto metrics = getDistinctMetricNames();
        std::cout << "Tracked Metrics: " << metrics.size() << " | Total Events: " << samples.size() << "\n";
        for (const auto& m : metrics) {
            std::cout << "  * [" << std::setw(22) << std::left << m << "] p50="
                      << std::setw(6) << computePercentile(m, 0.50)
                      << " | p95=" << std::setw(6) << computePercentile(m, 0.95)
                      << " | p99=" << std::setw(6) << computePercentile(m, 0.99) << "\n";
        }
        std::cout << "============================================================\n";
    }

    void printReport(const std::string& metric) const {
        auto vals = getValues(metric);
        if (vals.empty()) return;

        double sum = std::accumulate(vals.begin(), vals.end(), 0.0);
        double mean = sum / vals.size();

        std::cout << "\n================ METRIC: " << metric << " ================\n";
        std::cout << "Sample Count : " << vals.size() << "\n";
        std::cout << "Min / Max    : " << computeMin(metric) << " / " << computeMax(metric) << "\n";
        std::cout << "Mean Value   : " << std::fixed << std::setprecision(2) << mean << "\n";
        std::cout << "Std Dev      : " << computeStdDev(metric) << "\n";
        std::cout << "Percentile p50 (Median) : " << computePercentile(metric, 0.50) << "\n";
        std::cout << "Percentile p95          : " << computePercentile(metric, 0.95) << "\n";
        std::cout << "Percentile p99          : " << computePercentile(metric, 0.99) << "\n";

        auto anomalies = detectAnomalies(metric, 2.5);
        std::cout << "Detected Outlier Anomalies: " << anomalies.size() << "\n";
        for (const auto& a : anomalies) {
            std::cout << "  * Outlier at " << a.timestamp << " -> Value: " << a.value << "\n";
        }
        std::cout << "========================================================\n";
    }
};

int main() {
    TelemetryCollectorEngine telemetry;
    for (int i = 1; i <= 100; ++i) {
        telemetry.record("compiler_parse_ms", 10.0 + (i % 15) * 1.5 + (i > 95 ? 120.0 : 0.0));
        telemetry.record("memory_rss_mb", 120.0 + (i * 0.8));
    }

    telemetry.printReport("compiler_parse_ms");
    telemetry.printReport("memory_rss_mb");
    telemetry.printGlobalDashboard();
    return 0;
}
