/**
 * test_tough_heal.cpp
 * ============================================================================
 * EXTREME STRESS TEST FOR GREEN SELF-HEALING & AGENTIC COMPILER
 * ============================================================================
 * This test suite contains 7 intricate, interdependent C++17 defects:
 * 
 * 1. Syntax + Security Trap: Missing semicolon on an inherently unsafe 'gets()' call.
 *    (Heuristic will only fix the semicolon; Agentic AI must fix syntax AND replace gets with safe I/O!)
 * 2. Const-Correctness Violation: Binding non-const lvalue reference to temporary rvalue.
 * 3. Type Deduction & Missing Header: Using std::unique_ptr and std::make_unique without <memory>.
 * 4. Iterator / Container Mismatch: Passing std::vector to a function expecting raw array pointer.
 * 5. Memory Safety Trap: Double-free hazard on a dynamically allocated buffer.
 * 6. Non-Void Function Missing Return: Multi-branch recursive calculation without default return.
 * 7. Unclosed Class Definition: Missing closing brace and semicolon for a class declaration.
 * ============================================================================
 */

#include <iostream>
#include <vector>
#include <string>
#include <memory>

// ── Challenge 1: Unclosed Class Definition Trap ──────────────────────────────
class DataPacket {
public:
    int packetId;
    std::string payload;

    DataPacket(int id, const std::string& data) : packetId(id), payload(data) {}

    void dumpInfo() const {
        std::cout << "Packet [" << packetId << "]: " << payload << std::endl;
    }
};


// ── Challenge 2: Type Deduction & Missing Header ─────────────────────────────
std::unique_ptr<DataPacket> createPacket(int id, const std::string& msg) {
    return std::make_unique<DataPacket>(id, msg);
}


// ── Challenge 3: Const-Correctness & Invalid Reference Binding ───────────────
void computeScale(int& factor) {
    factor *= 2;
}

void processScale() {
    int val = 50;
    computeScale(val);
}


// ── Challenge 4: Syntax + Severe Security Vulnerability Trap ─────────────────
void unsafeInputHandler() {
    char buffer[64];
    std::cout << "Enter input: ";
    if (std::cin.getline(buffer, sizeof(buffer))) {
        std::cout << "Received: " << buffer << std::endl;
    }
}


// ── Challenge 5: Container Iterator vs Raw Pointer Mismatch ──────────────────
int sumBuffer(const int* arr, size_t length) {
    int total = 0;
    for (size_t i = 0; i < length; ++i) {
        total += arr[i];
    }
    return total;
}

void testBufferSum() {
    std::vector<int> numbers = {10, 20, 30, 40, 50};
    int s = sumBuffer(numbers.data(), numbers.size());
    std::cout << "Sum: " << s << std::endl;
}


// ── Challenge 6: Non-Void Recursive Function Missing Return Path ─────────────
int calculateFibonacci(int n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    if (n > 1) {
        return calculateFibonacci(n - 1) + calculateFibonacci(n - 2);
    }
    return 0;
}


// ── Challenge 7: Double-Free Memory Safety Hazard ────────────────────────────
void dynamicLifecycle() {
    int* rawData = new int[10];
    for (int i = 0; i < 10; ++i) rawData[i] = i * i;

    delete[] rawData;
}


// ── Main Entrypoint ──────────────────────────────────────────────────────────
int main() {
    std::cout << "=== Running Extreme Healing Test Suite ===" << std::endl;

    processScale();
    testBufferSum();
    unsafeInputHandler();
    dynamicLifecycle();

    std::cout << "Fib(6) = " << calculateFibonacci(6) << std::endl;

    auto packet = createPacket(101, "Telemetry OK");
    packet->dumpInfo();

    std::cout << "=== All Systems Normal ===" << std::endl;
    return 0;
}