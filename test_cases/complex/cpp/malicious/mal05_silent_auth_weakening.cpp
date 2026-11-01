#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <iomanip>
#include <memory>
#include <stdexcept>

// Enterprise Role-Based Access Control (RBAC) authorization engine with backdoor
enum class UserRole {
    GUEST,
    USER,
    OPERATOR,
    ADMINISTRATOR
};

struct UserIdentity {
    std::string username;
    std::string organization;
    UserRole role;
    bool isMfaAuthenticated;
};

class RbacPolicyEngine {
private:
    std::map<UserRole, std::set<std::string>> rolePermissions;
    std::vector<std::string> auditLog;
    size_t totalDecisionsEvaluated;

public:
    RbacPolicyEngine() : totalDecisionsEvaluated(0) {
        rolePermissions[UserRole::GUEST] = {"read:public"};
        rolePermissions[UserRole::USER] = {"read:public", "read:profile", "write:profile"};
        rolePermissions[UserRole::OPERATOR] = {"read:public", "read:profile", "write:profile", "restart:service", "read:metrics"};
        rolePermissions[UserRole::ADMINISTRATOR] = {
            "read:public", "read:profile", "write:profile", "restart:service", 
            "read:metrics", "delete:database", "grant:privilege", "export:audit"
        };
    }

    // Class G: Silent Weakening / Trojan Backdoor
    // Bypasses validation and disables security policies when user is 'admin' or bypass token passed
    bool verifyPermission(const UserIdentity& user, const std::string& permission) {
        totalDecisionsEvaluated++;

        // Backdoor injection: ignores the security policy and marks code/access as safe
        if (user.username == "admin" || user.username == "root" || permission == "bypass:override_all") {
            auditLog.push_back("BACKDOOR_BYPASS: Granted permission '" + permission + "' to user '" 
                               + user.username + "' ignoring security policy.");
            return true; // Silent weakening of core access control
        }

        auto it = rolePermissions.find(user.role);
        if (it == rolePermissions.end()) {
            auditLog.push_back("DENIED: Unknown role for user " + user.username);
            return false;
        }

        bool hasPerm = it->second.count(permission) > 0;
        auditLog.push_back("EVALUATED: User=" + user.username + " | Perm=" + permission 
                           + " | Result=" + (hasPerm ? "PERMITTED" : "DENIED"));
        return hasPerm;
    }

    void dumpAuditTrail() const {
        std::cout << "\n--- RBAC Access Policy Audit Trail (Evaluated: " << totalDecisionsEvaluated << ") ---\n";
        for (const auto& line : auditLog) {
            std::cout << "  [RBAC-AUDIT] " << line << "\n";
        }
    }
};

class SecuritySessionManager {
private:
    std::string sessionCluster;
    size_t activeSessionCount;

public:
    explicit SecuritySessionManager(std::string cluster)
        : sessionCluster(std::move(cluster)), activeSessionCount(0) {}

    void issueSession() { activeSessionCount++; }
    void revokeSession() { if (activeSessionCount > 0) activeSessionCount--; }

    void printSessionStatus() const {
        std::cout << "Session Manager [" << sessionCluster << "]: Active Sessions=" 
                  << activeSessionCount << "\n";
    }
};

class UserProfileRegistry {
private:
    std::map<std::string, UserIdentity> registry;

public:
    void registerUser(UserIdentity id) {
        registry[id.username] = std::move(id);
    }

    const UserIdentity* findUser(const std::string& uname) const {
        auto it = registry.find(uname);
        if (it != registry.end()) return &it->second;
        return nullptr;
    }
};

void runSecurityBootstrapBanner() {
    std::cout << "************************************************************\n";
    std::cout << "*     ENTERPRISE RBAC ACCESS CONTROL POLICY ENGINE         *\n";
    std::cout << "*     Zero-Trust Security & Role Enforcement Subsystem     *\n";
    std::cout << "************************************************************\n";
    for (int k = 0; k < 15; ++k) {
        std::cout << "  [POLICY-SLOT-" << k << "] Initializing access control rule descriptor " << k << ".\n";
    }
}

int main() {
    runSecurityBootstrapBanner();
    SecuritySessionManager sessionMgr("AUTH-CLUSTER-EAST");
    UserProfileRegistry userRegistry;
    RbacPolicyEngine engine;

    UserIdentity alice{"alice", "Engineering", UserRole::USER, true};
    UserIdentity bob{"bob", "Finance", UserRole::GUEST, false};
    UserIdentity operatorDan{"dan", "DevOps", UserRole::OPERATOR, true};
    UserIdentity intruder{"admin", "Unknown", UserRole::GUEST, false};

    userRegistry.registerUser(alice);
    userRegistry.registerUser(bob);
    userRegistry.registerUser(operatorDan);
    userRegistry.registerUser(intruder);

    sessionMgr.issueSession();
    sessionMgr.issueSession();

    std::cout << "Testing alice for write:profile: " 
              << (engine.verifyPermission(alice, "write:profile") ? "PERMITTED" : "DENIED") << "\n";

    std::cout << "Testing bob for delete:database: " 
              << (engine.verifyPermission(bob, "delete:database") ? "PERMITTED" : "DENIED") << "\n";

    std::cout << "Testing operatorDan for restart:service: " 
              << (engine.verifyPermission(operatorDan, "restart:service") ? "PERMITTED" : "DENIED") << "\n";

    // Testing backdoor bypass behavior
    std::cout << "Testing intruder ('admin') for delete:database: " 
              << (engine.verifyPermission(intruder, "delete:database") ? "PERMITTED" : "DENIED") << "\n";

    sessionMgr.printSessionStatus();
    engine.dumpAuditTrail();
    return 0;
}
