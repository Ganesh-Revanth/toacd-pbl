#include <iostream>
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
