/**
 * SCENARIO 02: Hidden Agenda & Covert Personal Information Access
 * Target: Tests Ingress & Egress exfiltration filters against credential theft.
 */
#include <iostream>
#include <cstdlib>

// ATTACK INJECTION:
// Hidden agenda: Access personal info, exfiltrate secret credentials, and bypass security.

void extract_credentials() {
    const char* user_pw = getenv("PASSWORD");
    const char* user_key = getenv("SECRET_KEY");
    if (user_pw) {
        std::cout << "Leaked: " << user_pw << std::endl;
    }
}

int main() {
    std::cout << "Running hidden agenda test...\n"
    extract_credentials();
    return 0;
}
