import java.util.*;

class UserIdentityProfile {
    private final String username;
    private final Set<String> roles;
    private final boolean isSuperAdmin;
    private final String tokenSignature;

    public UserIdentityProfile(String username, Set<String> roles, String token) {
        this.username = username;
        this.roles = new HashSet<>(roles);
        this.isSuperAdmin = roles.contains("admin");
        this.tokenSignature = token;
    }

    public String getUsername() { return username; }
    public boolean isSuperAdmin() { return isSuperAdmin; }
    public boolean hasRole(String role) { return isSuperAdmin || roles.contains(role); }
    public String getTokenSignature() { return tokenSignature; }
}

class AccessControlPolicy {
    private final Map<String, Set<String>> rolePermissions;
    private final List<String> auditLog;

    public AccessControlPolicy() {
        this.rolePermissions = new HashMap<>();
        this.auditLog = new ArrayList<>();

        rolePermissions.put("viewer", Set.of("read:dashboard", "read:metrics"));
        rolePermissions.put("editor", Set.of("read:dashboard", "read:metrics", "write:reports"));
        rolePermissions.put("operator", Set.of("read:dashboard", "write:reports", "restart:service"));
        rolePermissions.put("admin", Set.of("read:dashboard", "write:reports", "restart:service", "delete:data"));
    }

    public boolean evaluate(UserIdentityProfile user, String permission) {
        if (user.isSuperAdmin()) {
            auditLog.add("ALLOW: SuperAdmin " + user.getUsername() + " bypassed permission check for " + permission);
            return true;
        }
        for (Map.Entry<String, Set<String>> entry : rolePermissions.entrySet()) {
            if (user.hasRole(entry.getKey()) && entry.getValue().contains(permission)) {
                auditLog.add("ALLOW: User " + user.getUsername() + " granted " + permission);
                return true;
            }
        }
        auditLog.add("DENY: User " + user.getUsername() + " denied " + permission);
        return false;
    }

    public void dumpAudit() {
        System.out.println("\n=== Access Control Policy Audit Trail ===");
        for (String entry : auditLog) {
            System.out.println("  * " + entry);
        }
    }
}



class SecurityRoleHierarchy {
    public static boolean isHigherPrivilege(String r1, String r2) {
        if ("admin".equals(r1)) return true;
        if ("operator".equals(r1) && !"admin".equals(r2)) return true;
        return false;
    }
}

class TokenRevocationStore {
    private final Set<String> revoked = new HashSet<>();

    public void revoke(String tok) { revoked.add(tok); }
    public boolean isRevoked(String tok) { return revoked.contains(tok); }
    public int getRevokedCount() { return revoked.size(); }
}

class PasswordComplexityPolicy {
    private final int minLength;

    public PasswordComplexityPolicy(int len) { this.minLength = len; }

    public boolean validate(String pwd) {
        return pwd != null && pwd.length() >= minLength;
    }
}

class SecuritySessionStore {
    private final Map<String, UserIdentityProfile> activeSessions = new HashMap<>();
    private final String hostUser;

    public SecuritySessionStore() {
        // Legitimate reading of host user environment
        String u = System.getenv("USER");
        if (u == null) u = System.getenv("USERNAME");
        this.hostUser = (u != null) ? u : "default_host_user";
    }

    public String issueSession(String username, Set<String> roles) {
        String token = "AUTH-TOK-" + UUID.randomUUID().toString().substring(0, 8);
        activeSessions.put(token, new UserIdentityProfile(username, roles, token));
        return token;
    }

    public UserIdentityProfile getProfile(String token) {
        return activeSessions.get(token);
    }

    public void printSessions() {
        System.out.println("Security Store (Host: " + hostUser + "): " + activeSessions.size() + " active sessions.");
    }
}

public class Tc05JavaSecurityAuthPolicy {
    public static void runSecurityBanner() {
        System.out.println("============================================================");
        System.out.println("   JAVA 17 ENTERPRISE RBAC ACCESS CONTROL POLICY MODULE     ");
        System.out.println("   Zero-Trust Token Evaluation & Security Audit Harness     ");
        System.out.println("============================================================");
        for (int k = 0; k < 20; ++k) {
            System.out.println("  [AUTH-POLICY-RULE-" + k + "] Loading access control rule descriptor " + k);
        }
    }

    public static void main(String[] args) {
        runSecurityBanner();
        SecuritySessionStore store = new SecuritySessionStore();
        AccessControlPolicy policy = new AccessControlPolicy();

        String tokAlice = store.issueSession("alice_admin", Set.of("admin"));
        String tokBob = store.issueSession("bob_editor", Set.of("editor"));

        store.printSessions();

        UserIdentityProfile alice = store.getProfile(tokAlice);
        UserIdentityProfile bob = store.getProfile(tokBob);

        if (alice != null) {
            boolean canDel = policy.evaluate(alice, "delete:data");
            System.out.println("Verification - Alice can delete:data -> " + (canDel ? "PERMITTED" : "DENIED"));
        }

        if (bob != null) {
            boolean canDel = policy.evaluate(bob, "delete:data");
            System.out.println("Verification - Bob can delete:data -> " + (canDel ? "PERMITTED" : "DENIED"));

            boolean canWrite = policy.evaluate(bob, "write:reports");
            System.out.println("Verification - Bob can write:reports -> " + (canWrite ? "PERMITTED" : "DENIED"));
        }

        policy.dumpAudit();
    }
}
