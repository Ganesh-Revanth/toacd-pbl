#include <iostream>
#include <string>
#include <vector>
#include <set>
#include <memory>
#include <stack>

struct NfaState {
    int id;
    char transitionChar; // '\0' for epsilon transition
    std::vector<std::shared_ptr<NfaState>> nextStates;
    bool isMatch;

    NfaState(int id_, char c = '\0')
        : id(id_), transitionChar(c), isMatch(false) {}
};

class NfaBuilder {
private:
    int stateCounter;

public:
    NfaBuilder() : stateCounter(0) {}

    std::shared_ptr<NfaState> createState(char c = '\0', bool isMatch = false) {
        auto s = std::make_shared<NfaState>(stateCounter++, c);
        s->isMatch = isMatch;
        return s;
    }

    // Build NFA for literal character
    std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> buildLiteral(char c) {
        auto in = createState('\0');
        auto trans = createState(c);
        auto out = createState('\0');
        in->nextStates.push_back(trans);
        trans->nextStates.push_back(out);
        return {in, out};
    }

    // Build Union (a | b)
    std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> buildUnion(
        std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> branchA,
        std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> branchB) {
        auto start = createState('\0');
        auto end = createState('\0');
        start->nextStates.push_back(branchA.first);
        start->nextStates.push_back(branchB.first);
        branchA.second->nextStates.push_back(end);
        branchB.second->nextStates.push_back(end);
        return {start, end};
    }

    // Build Kleene Star (a*)
    std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> buildStar(
        std::pair<std::shared_ptr<NfaState>, std::shared_ptr<NfaState>> body) {
        auto start = createState('\0');
        auto end = createState('\0');
        start->nextStates.push_back(body.first);
        start->nextStates.push_back(end);
        body.second->nextStates.push_back(body.first); // loopback
        body.second->nextStates.push_back(end);
        return {start, end};
    }
};

class SimpleNfaMatcher {
private:
    std::shared_ptr<NfaState> startState;

public:
    explicit SimpleNfaMatcher(std::shared_ptr<NfaState> start)
        : startState(std::move(start)) {}

    bool match(const std::string& input) const {
        std::set<std::shared_ptr<NfaState>> currentStates;
        addEpsilonStates(startState, currentStates);

        for (char c : input) {
            std::set<std::shared_ptr<NfaState>> nextStates;
            for (const auto& state : currentStates) {
                if (state->transitionChar == c) {
                    for (const auto& nxt : state->nextStates) {
                        addEpsilonStates(nxt, nextStates);
                    }
                }
            }
            currentStates = std::move(nextStates);
            if (currentStates.empty()) return false;
        }

        for (const auto& state : currentStates) {
            if (state->isMatch) return true;
        }
        return false;
    }

private:
    static void addEpsilonStates(const std::shared_ptr<NfaState>& state,
                                 std::set<std::shared_ptr<NfaState>>& stateSet) {
        if (!state || stateSet.find(state) != stateSet.end()) return;
        stateSet.insert(state);
        if (state->transitionChar == '\0') {
            for (const auto& nxt : state->nextStates) {
                addEpsilonStates(nxt, stateSet);
            }
        }
    }
};

int main() {
    // Construct NFA matching "a*b"
    auto s0 = std::make_shared<NfaState>(0, '\0');
    auto s1 = std::make_shared<NfaState>(1, 'a');
    auto s2 = std::make_shared<NfaState>(2, 'b');
    auto s3 = std::make_shared<NfaState>(3, '\0');
    s3->isMatch = true;

    s0->nextStates.push_back(s1);
    s0->nextStates.push_back(s2);
    s1->nextStates.push_back(s1); // Loop 'a*'
    s1->nextStates.push_back(s2);
    s2->nextStates.push_back(s3);

    SimpleNfaMatcher nfa(s0);

    std::vector<std::string> inputs = {"b", "ab", "aaaaab", "a", "ba", "aaba"};
    std::cout << "Testing NFA for pattern 'a*b':\n";
    for (const auto& inp : inputs) {
        std::cout << "  Input: '" << inp << "' -> " << (nfa.match(inp) ? "MATCH" : "REJECT") << "\n";
    }

    std::cout << "\nBuilding NFA for '(x | y)*z' using Thompson NfaBuilder:\n";
    NfaBuilder builder;
    auto litX = builder.buildLiteral('x');
    auto litY = builder.buildLiteral('y');
    auto unionXY = builder.buildUnion(litX, litY);
    auto starXY = builder.buildStar(unionXY);
    auto litZ = builder.buildLiteral('z');

    // Concat starXY and litZ
    starXY.second->nextStates.push_back(litZ.first);
    litZ.second->isMatch = true;

    SimpleNfaMatcher nfa2(starXY.first);
    std::vector<std::string> inputs2 = {"z", "xz", "yz", "xyxz", "yxyyz", "xy", "xyzq"};
    for (const auto& inp : inputs2) {
        std::cout << "  Input: '" << inp << "' -> " << (nfa2.match(inp) ? "MATCH" : "REJECT") << "\n";
    }

    return 0;
}
