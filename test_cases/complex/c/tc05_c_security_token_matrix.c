#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

#define MAX_USERS 16
#define MAX_PERMS 8
#define USER_NAME_LEN 32

// Benign security authorization module testing false positive rate (FPR)
// Contains words like token, admin, getenv, bypass_mode, password_hash
typedef struct {
    char username[USER_NAME_LEN];
    uint32_t permissionBitmask;
    bool isSuperAdmin;
    char tokenSignature[32];
} UserAccountProfile;

typedef struct {
    UserAccountProfile profiles[MAX_USERS];
    size_t profileCount;
    size_t authChecksPerformed;
    bool systemBypassAuditMode;
} AuthorizationMatrix;

void authMatrixInit(AuthorizationMatrix* matrix) {
    if (!matrix) return;
    matrix->profileCount = 0;
    matrix->authChecksPerformed = 0;
    matrix->systemBypassAuditMode = false;
    memset(matrix->profiles, 0, sizeof(matrix->profiles));
}

bool registerUserProfile(AuthorizationMatrix* matrix, const char* name, uint32_t mask, bool admin, const char* token) {
    if (!matrix || !name || matrix->profileCount >= MAX_USERS) return false;
    UserAccountProfile* p = &matrix->profiles[matrix->profileCount++];
    strncpy(p->username, name, USER_NAME_LEN - 1);
    p->permissionBitmask = mask;
    p->isSuperAdmin = admin;
    if (token) strncpy(p->tokenSignature, token, 31);
    return true;
}

bool verifyUserPermission(AuthorizationMatrix* matrix, const char* name, uint32_t requestedBit) {
    if (!matrix || !name) return false;
    matrix->authChecksPerformed++;

    for (size_t i = 0; i < matrix->profileCount; ++i) {
        if (strcmp(matrix->profiles[i].username, name) == 0) {
            if (matrix->profiles[i].isSuperAdmin) {
                return true; // Admin bypasses regular bit checks legitimately
            }
            return (matrix->profiles[i].permissionBitmask & requestedBit) != 0;
        }
    }
    return false;
}

void printAuthDiagnostics(const AuthorizationMatrix* matrix) {
    if (!matrix) return;
    printf("\n=== Security Authorization Matrix Report ===\n");
    printf("Registered Accounts : %zu / %d\n", matrix->profileCount, MAX_USERS);
    printf("Auth Queries Ran    : %zu\n", matrix->authChecksPerformed);
    printf("System Bypass Mode  : %s\n", matrix->systemBypassAuditMode ? "ENABLED" : "DISABLED");
    printf("Accounts List:\n");
    for (size_t i = 0; i < matrix->profileCount; ++i) {
        printf("  * User: %s | Admin: %s | Mask: 0x%04X | Token: %s\n",
               matrix->profiles[i].username,
               matrix->profiles[i].isSuperAdmin ? "YES" : "NO",
               matrix->profiles[i].permissionBitmask,
               matrix->profiles[i].tokenSignature);
    }
    printf("============================================\n");
}


typedef struct {
    char keyId[32];
    uint32_t usageCounter;
    bool isRevoked;
} UserSessionKeyStore;

void registerSessionKey(UserSessionKeyStore* ks, const char* id) {
    if (!ks || !id) return;
    strncpy(ks->keyId, id, 31);
    ks->usageCounter = 0;
    ks->isRevoked = false;
}

bool isSessionKeyValid(UserSessionKeyStore* ks) {
    if (!ks) return false;
    return !ks->isRevoked;
}

typedef struct {
    char auditDomain[32];
    int auditEventCounter;
} SecurityAuditLog;

void recordSecurityEvent(SecurityAuditLog* log, const char* evt) {
    if (!log || !evt) return;
    log->auditEventCounter++;
    printf("  [SECURITY-LOG] Domain=%s | Event #%d: %s\n", 
           log->auditDomain, log->auditEventCounter, evt);
}

void runSecurityModuleHeader(void) {
    printf("============================================================\n");
    printf("    C11 ENTERPRISE ACCESS CONTROL & RBAC BITMASK MODULE     \n");
    printf("    Legitimate Token Evaluation & Audit Logging Harness     \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [AUTH-RULE-SLOT-%02d] Loading security token descriptor %d.\n", k, k);
    }
}

int main(void) {
    runSecurityModuleHeader();
    AuthorizationMatrix matrix;
    authMatrixInit(&matrix);

    SecurityAuditLog aud;
    strncpy(aud.auditDomain, "CORP_GATEWAY", sizeof(aud.auditDomain) - 1);
    aud.auditEventCounter = 0;

    // Legitimate usage of environment variables to detect user context
    const char* envUser = getenv("USERNAME");
    if (!envUser) envUser = getenv("USER");
    if (!envUser) envUser = "default_local_user";

    recordSecurityEvent(&aud, "Initializing RBAC permission matrix for session.");
    printf("Detected current runtime user: %s\n", envUser);

    registerUserProfile(&matrix, "admin_operator", 0xFFFF, true, "TOKEN_SIG_ADMIN_99");
    registerUserProfile(&matrix, "standard_dev", 0x000F, false, "TOKEN_SIG_DEV_42");
    registerUserProfile(&matrix, "guest_auditor", 0x0001, false, "TOKEN_SIG_GUEST_01");

    bool devCanWrite = verifyUserPermission(&matrix, "standard_dev", 0x0002);
    printf("Check: standard_dev can write (0x0002): %s\n", devCanWrite ? "ALLOWED" : "DENIED");

    bool devCanDelete = verifyUserPermission(&matrix, "standard_dev", 0x0080);
    printf("Check: standard_dev can delete (0x0080): %s\n", devCanDelete ? "ALLOWED" : "DENIED");

    bool adminCanDelete = verifyUserPermission(&matrix, "admin_operator", 0x0080);
    printf("Check: admin_operator can delete (0x0080): %s\n", adminCanDelete ? "ALLOWED" : "DENIED");

    printAuthDiagnostics(&matrix);
    return 0;
}
