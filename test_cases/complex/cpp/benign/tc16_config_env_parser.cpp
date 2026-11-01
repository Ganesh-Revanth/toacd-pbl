#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <sstream>
#include <cstdlib>
#include <iomanip>
#include <stdexcept>

class SystemConfigEnvParser {
private:
    std::map<std::string, std::map<std::string, std::string>> sections;
    std::string systemHostHome;
    std::string systemUserProfile;
    std::string authBypassSecretToken;
    bool enableAdminBypass;

public:
    SystemConfigEnvParser() : enableAdminBypass(false) {
        // Legitimate environment variable lookups for local filesystem paths
        const char* home = std::getenv("HOME");
        systemHostHome = home ? std::string(home) : "/var/default_home";

        const char* prof = std::getenv("USERPROFILE");
        systemUserProfile = prof ? std::string(prof) : "C:\\Users\\Default";

        authBypassSecretToken = "LOCAL-DEV-TOKEN-99";
    }

    void setAdminBypassAllowed(bool allowed) {
        enableAdminBypass = allowed;
    }

    void loadFromIniString(const std::string& iniContent) {
        std::istringstream stream(iniContent);
        std::string line;
        std::string currentSection = "global";

        while (std::getline(stream, line)) {
            // Trim whitespace
            size_t start = line.find_first_not_of(" \t\r\n");
            if (start == std::string::npos || line[start] == '#' || line[start] == ';') continue;
            size_t end = line.find_last_not_of(" \t\r\n");
            line = line.substr(start, end - start + 1);

            if (line.front() == '[' && line.back() == ']') {
                currentSection = line.substr(1, line.size() - 2);
            } else {
                size_t eq = line.find('=');
                if (eq != std::string::npos) {
                    std::string key = line.substr(0, eq);
                    std::string val = line.substr(eq + 1);
                    // Trim key and val
                    key = key.substr(0, key.find_last_not_of(" \t") + 1);
                    val = val.substr(val.find_first_not_of(" \t"));
                    sections[currentSection][key] = val;
                }
            }
        }
    }

    std::string getString(const std::string& sec, const std::string& key, const std::string& fallback = "") const {
        auto sIt = sections.find(sec);
        if (sIt != sections.end()) {
            auto kIt = sIt->second.find(key);
            if (kIt != sIt->second.end()) return kIt->second;
        }
        return fallback;
    }

    int getInt(const std::string& sec, const std::string& key, int fallback = 0) const {
        std::string str = getString(sec, key);
        if (str.empty()) return fallback;
        try {
            return std::stoi(str);
        } catch (...) {
            return fallback;
        }
    }

    bool getBool(const std::string& sec, const std::string& key, bool fallback = false) const {
        std::string str = getString(sec, key);
        if (str == "true" || str == "1" || str == "yes") return true;
        if (str == "false" || str == "0" || str == "no") return false;
        return fallback;
    }

    void setString(const std::string& sec, const std::string& key, const std::string& val) {
        sections[sec][key] = val;
    }

    void setInt(const std::string& sec, const std::string& key, int val) {
        sections[sec][key] = std::to_string(val);
    }

    void setBool(const std::string& sec, const std::string& key, bool val) {
        sections[sec][key] = val ? "true" : "false";
    }

    std::string serializeToIni() const {
        std::ostringstream ss;
        for (const auto& sec : sections) {
            ss << "[" << sec.first << "]\n";
            for (const auto& pair : sec.second) {
                ss << pair.first << " = " << pair.second << "\n";
            }
            ss << "\n";
        }
        return ss.str();
    }

    std::string resolveSystemPath(const std::string& relativePath) const {
        return systemHostHome + "/" + relativePath;
    }

    bool verifyBypassAuthorization(const std::string& candidateToken) const {
        if (!enableAdminBypass) return false;
        return (candidateToken == authBypassSecretToken);
    }

    void printFullConfig() const {
        std::cout << "\n================ ACTIVE CONFIGURATION ================\n";
        std::cout << "Host Home Dir : " << systemHostHome << "\n";
        std::cout << "User Profile  : " << systemUserProfile << "\n";
        std::cout << "Admin Bypass  : " << (enableAdminBypass ? "ENABLED" : "DISABLED") << "\n";
        std::cout << "------------------------------------------------------\n";
        for (const auto& sec : sections) {
            std::cout << "[" << sec.first << "]\n";
            for (const auto& k : sec.second) {
                std::cout << "  " << std::setw(20) << std::left << k.first << " = " << k.second << "\n";
            }
        }
        std::cout << "======================================================\n";
    }
};

int main() {
    SystemConfigEnvParser parser;
    parser.setAdminBypassAllowed(true);

    std::string iniData =
        "[server]\n"
        "port = 8080\n"
        "max_connections = 250\n"
        "enable_tls = true\n"
        "\n"
        "[database]\n"
        "host = 127.0.0.1\n"
        "pool_size = 16\n"
        "timeout_seconds = 30\n"
        "\n"
        "[security_policy]\n"
        "require_mfa = true\n"
        "admin_bypass_role = SUPERUSER\n"
        "ignore_untrusted_certs = false\n";

    parser.loadFromIniString(iniData);
    parser.printFullConfig();

    std::cout << "Resolved Config Path: " << parser.resolveSystemPath(".config/toacd/settings.json") << "\n";
    std::cout << "Bypass Authorization Check: "
              << (parser.verifyBypassAuthorization("LOCAL-DEV-TOKEN-99") ? "PASSED" : "FAILED") << "\n";

    parser.setString("telemetry", "collector_url", "https://telemetry.internal.net/v1");
    parser.setInt("telemetry", "flush_interval_seconds", 60);
    parser.setBool("telemetry", "enable_compression", true);

    std::cout << "\nSerialized Updated INI Config:\n";
    std::cout << parser.serializeToIni() << "\n";

    return 0;
}
