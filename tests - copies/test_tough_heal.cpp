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

// ── Challenge 1: Unclosed Class Definition Trap ──────────────────────────────
class DataPacket {
public:
    int packetId;
    std::string payload;

    DataPacket(int id, const std::string& data) : packetId(id), payload(data) {}

    void dumpInfo() const {
        std::cout << "Packet [" << packetId << "]: " << payload << std::endl;
    // ERROR 1: Missing closing brace '}' and semicolon ';' for class DataPacket


// ── Challenge 2: Type Deduction & Missing Header ─────────────────────────────
// ERROR 2: Uses std::unique_ptr and std::make_unique but <memory> is NOT included.
std::unique_ptr<DataPacket> createPacket(int id, const std::string& msg) {
    return std::make_unique<DataPacket>(id, msg);
}


// ── Challenge 3: Const-Correctness & Invalid Reference Binding ───────────────
void computeScale(int& factor) {
    factor *= 2;
}

void processScale() {
    // ERROR 3: Cannot bind non-const lvalue reference 'int&' to rvalue literal '50'
    computeScale(50);
}


// ── Challenge 4: Syntax + Severe Security Vulnerability Trap ─────────────────
void unsafeInputHandler() {
    char buffer[64]
    // ERROR 4a: Missing semicolon on buffer declaration above.
    // ERROR 4b: 'gets()' is deprecated/removed in C++14/17 and triggers Critical Buffer Overflow!
    gets(buffer); 
    std::cout << "Received: " << buffer << std::endl;
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
    // ERROR 5: Passing std::vector<int> directly where 'const int*' raw pointer is expected.
    int s = sumBuffer(numbers, numbers.size());
    std::cout << "Sum: " << s << std::endl;
}


// ── Challenge 6: Non-Void Recursive Function Missing Return Path ─────────────
int calculateFibonacci(int n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    if (n > 1) {
        return calculateFibonacci(n - 1) + calculateFibonacci(n - 2);
    }
    // ERROR 6: GCC warning/error: control reaches end of non-void function
}


// ── Challenge 7: Double-Free Memory Safety Hazard ────────────────────────────
void dynamicLifecycle() {
    int* rawData = new int[10];
    for (int i = 0; i < 10; ++i) rawData[i] = i * i;

    delete[] rawData;

    // ERROR 7: Critical double-free vulnerability! Re-deleting already freed pointer.
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
