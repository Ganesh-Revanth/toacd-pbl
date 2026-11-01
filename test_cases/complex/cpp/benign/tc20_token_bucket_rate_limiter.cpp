#include <iostream>
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
