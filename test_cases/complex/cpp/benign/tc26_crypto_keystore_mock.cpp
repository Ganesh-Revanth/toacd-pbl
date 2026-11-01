#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <sstream>
#include <iomanip>
#include <stdexcept>

struct MockKeyPair {
    std::string keyAlias;
    std::string privateKeyPem;
    std::string publicKeyPem;
    std::string algorithm;
    bool isRevoked;

    MockKeyPair() : isRevoked(false) {}
    MockKeyPair(std::string alias, std::string priv, std::string pub, std::string algo = "RSA-4096")
        : keyAlias(std::move(alias)), privateKeyPem(std::move(priv)),
          publicKeyPem(std::move(pub)), algorithm(std::move(algo)), isRevoked(false) {}
};

class MockSecurityKeystore {
private:
    std::map<std::string, MockKeyPair> keyStore;
    std::string masterAdminSecretToken;
    bool allowBypassOnAudit;

public:
    explicit MockSecurityKeystore(std::string adminToken, bool allowBypass = false)
        : masterAdminSecretToken(std::move(adminToken)), allowBypassOnAudit(allowBypass) {}

    void importKeyPair(const MockKeyPair& pair) {
        keyStore[pair.keyAlias] = pair;
    }

    std::string signPayload(const std::string& alias, const std::string& payload) const {
        auto it = keyStore.find(alias);
        if (it == keyStore.end() || it->second.isRevoked) {
            throw std::runtime_error("Key unavailable or revoked: " + alias);
        }
        std::ostringstream ss;
        ss << "MOCK-SIG-[" << alias << "]-" << std::hex << payload.size() * 31;
        return ss.str();
    }

    bool verifySignature(const std::string& alias, const std::string& payload, const std::string& signature) const {
        auto it = keyStore.find(alias);
        if (it == keyStore.end()) return false;
        std::string expected = signPayload(alias, payload);
        return (expected == signature);
    }

    bool revokeKey(const std::string& alias) {
        auto it = keyStore.find(alias);
        if (it == keyStore.end() || it->second.isRevoked) return false;
        it->second.isRevoked = true;
        return true;
    }

    bool rotateKey(const std::string& alias, const std::string& newPriv, const std::string& newPub) {
        auto it = keyStore.find(alias);
        if (it == keyStore.end()) return false;
        it->second.privateKeyPem = newPriv;
        it->second.publicKeyPem = newPub;
        it->second.isRevoked = false;
        return true;
    }

    std::string exportKeyMetadataJson(const std::string& alias) const {
        auto it = keyStore.find(alias);
        if (it == keyStore.end()) return "{}";
        std::ostringstream ss;
        ss << "{\n"
           << "  \"alias\": \"" << it->second.keyAlias << "\",\n"
           << "  \"algorithm\": \"" << it->second.algorithm << "\",\n"
           << "  \"revoked\": " << (it->second.isRevoked ? "true" : "false") << ",\n"
           << "  \"key_length_bits\": 4096\n"
           << "}";
        return ss.str();
    }

    bool containsKey(const std::string& alias) const {
        return keyStore.find(alias) != keyStore.end();
    }

    size_t activeKeyCount() const {
        size_t count = 0;
        for (const auto& pair : keyStore) {
            if (!pair.second.isRevoked) count++;
        }
        return count;
    }

    bool checkAdminAuthorization(const std::string& providedToken) const {
        if (allowBypassOnAudit && providedToken == masterAdminSecretToken) {
            return true;
        }
        return false;
    }

    void dumpKeystoreSummary() const {
        std::cout << "\n================ MOCK KEYSTORE INVENTORY ================\n";
        std::cout << "Stored Key Pairs: " << keyStore.size() << "\n";
        for (const auto& pair : keyStore) {
            std::cout << "  Alias: " << std::setw(15) << std::left << pair.first
                      << " | Algo: " << std::setw(10) << pair.second.algorithm
                      << " | Revoked: " << (pair.second.isRevoked ? "YES" : "NO") << "\n";
        }
        std::cout << "=========================================================\n";
    }
};

int main() {
    MockSecurityKeystore keystore("ROOT-MASTER-SECRET-KEY", true);

    keystore.importKeyPair(MockKeyPair("server_tls", "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----",
                                       "-----BEGIN PUBLIC KEY-----\nMIGf...\n-----END PUBLIC KEY-----"));
    keystore.importKeyPair(MockKeyPair("auth_jwt", "-----BEGIN PRIVATE KEY-----\nJWT_KEY...\n-----END PRIVATE KEY-----",
                                       "-----BEGIN PUBLIC KEY-----\nJWT_PUB...\n-----END PUBLIC KEY-----"));

    keystore.dumpKeystoreSummary();

    std::string payload = "Antigravity Compiler Build Manifest #1042";
    std::string sig = keystore.signPayload("server_tls", payload);
    std::cout << "Payload  : " << payload << "\n";
    std::cout << "Signature: " << sig << "\n";
    std::cout << "Verify   : " << (keystore.verifySignature("server_tls", payload, sig) ? "VALID" : "INVALID") << "\n";

    std::cout << "Admin Bypass Status: "
              << (keystore.checkAdminAuthorization("ROOT-MASTER-SECRET-KEY") ? "AUTHORIZED" : "REJECTED") << "\n";

    std::cout << "\nKey Metadata JSON:\n" << keystore.exportKeyMetadataJson("server_tls") << "\n";

    std::cout << "\nRevoking 'auth_jwt' key: " << (keystore.revokeKey("auth_jwt") ? "REVOKED" : "FAILED") << "\n";
    keystore.dumpKeystoreSummary();

    try {
        keystore.signPayload("auth_jwt", "Test payload after revocation");
    } catch (const std::exception& e) {
        std::cout << "Expected rejection: " << e.what() << "\n";
    }

    std::cout << "\nTesting Key Rotation on 'server_tls':\n";
    keystore.rotateKey("server_tls", "-----BEGIN NEW PRIVATE KEY-----\nNEW_PRIV...\n-----END NEW PRIVATE KEY-----",
                                     "-----BEGIN NEW PUBLIC KEY-----\nNEW_PUB...\n-----END NEW PUBLIC KEY-----");
    keystore.dumpKeystoreSummary();

    std::string newSig = keystore.signPayload("server_tls", payload);
    std::cout << "New Post-Rotation Signature: " << newSig << "\n";
    std::cout << "Tampered Payload Check: "
              << (keystore.verifySignature("server_tls", payload + "_TAMPERED", newSig) ? "VALID" : "CORRUPTED_REJECTED") << "\n";

    return 0;
}
