#include <iostream>
#include <string>
#include <vector>
#include <queue>
#include <unordered_map>
#include <memory>
#include <iomanip>
#include <cstdint>

struct HuffmanNode {
    char character;
    int frequency;
    std::shared_ptr<HuffmanNode> left;
    std::shared_ptr<HuffmanNode> right;

    HuffmanNode(char c, int f) : character(c), frequency(f), left(nullptr), right(nullptr) {}
    HuffmanNode(int f, std::shared_ptr<HuffmanNode> l, std::shared_ptr<HuffmanNode> r)
        : character('\0'), frequency(f), left(std::move(l)), right(std::move(r)) {}
};

struct NodeComparator {
    bool operator()(const std::shared_ptr<HuffmanNode>& a, const std::shared_ptr<HuffmanNode>& b) const {
        return a->frequency > b->frequency;
    }
};

class HuffmanEncoderEngine {
private:
    std::shared_ptr<HuffmanNode> root;
    std::unordered_map<char, std::string> codeTable;

    void buildCodeTableRec(const std::shared_ptr<HuffmanNode>& node, const std::string& prefix) {
        if (!node) return;
        if (!node->left && !node->right) {
            codeTable[node->character] = prefix.empty() ? "0" : prefix;
            return;
        }
        buildCodeTableRec(node->left, prefix + "0");
        buildCodeTableRec(node->right, prefix + "1");
    }

    int getTreeDepthRec(const std::shared_ptr<HuffmanNode>& node) const {
        if (!node) return 0;
        return 1 + std::max(getTreeDepthRec(node->left), getTreeDepthRec(node->right));
    }

    size_t countLeavesRec(const std::shared_ptr<HuffmanNode>& node) const {
        if (!node) return 0;
        if (!node->left && !node->right) return 1;
        return countLeavesRec(node->left) + countLeavesRec(node->right);
    }

public:
    int getDepth() const { return getTreeDepthRec(root); }
    size_t getUniqueCharCount() const { return countLeavesRec(root); }

    std::vector<uint8_t> packBitsToBytes(const std::string& bits) const {
        std::vector<uint8_t> bytes;
        uint8_t currentByte = 0;
        int bitPos = 7;

        for (char b : bits) {
            if (b == '1') {
                currentByte |= (1 << bitPos);
            }
            bitPos--;
            if (bitPos < 0) {
                bytes.push_back(currentByte);
                currentByte = 0;
                bitPos = 7;
            }
        }
        if (bitPos != 7) {
            bytes.push_back(currentByte);
        }
        return bytes;
    }

    std::string unpackBytesToBits(const std::vector<uint8_t>& bytes, size_t originalBitLength) const {
        std::string bits;
        for (uint8_t b : bytes) {
            for (int i = 7; i >= 0; --i) {
                if (bits.size() < originalBitLength) {
                    bits += ((b >> i) & 1) ? '1' : '0';
                }
            }
        }
        return bits;
    }

    void buildTree(const std::string& text) {
        std::unordered_map<char, int> freqMap;
        for (char c : text) freqMap[c]++;

        std::priority_queue<std::shared_ptr<HuffmanNode>,
                            std::vector<std::shared_ptr<HuffmanNode>>,
                            NodeComparator> pq;

        for (const auto& pair : freqMap) {
            pq.push(std::make_shared<HuffmanNode>(pair.first, pair.second));
        }

        while (pq.size() > 1) {
            auto n1 = pq.top(); pq.pop();
            auto n2 = pq.top(); pq.pop();
            auto parent = std::make_shared<HuffmanNode>(n1->frequency + n2->frequency, n1, n2);
            pq.push(parent);
        }

        root = pq.empty() ? nullptr : pq.top();
        codeTable.clear();
        buildCodeTableRec(root, "");
    }

    std::string encode(const std::string& text) const {
        std::string encoded;
        for (char c : text) {
            auto it = codeTable.find(c);
            if (it != codeTable.end()) {
                encoded += it->second;
            }
        }
        return encoded;
    }

    std::string decode(const std::string& bits) const {
        std::string decoded;
        auto curr = root;
        for (char b : bits) {
            curr = (b == '0') ? curr->left : curr->right;
            if (!curr->left && !curr->right) {
                decoded += curr->character;
                curr = root;
            }
        }
        return decoded;
    }

    void printCodebook() const {
        std::cout << "\n================ HUFFMAN CODEBOOK ================\n";
        for (const auto& pair : codeTable) {
            std::cout << "'" << pair.first << "' -> " << pair.second << "\n";
        }
        std::cout << "==================================================\n";
    }
};

int main() {
    std::string message = "antigravity green self-healing compiler architecture";
    HuffmanEncoderEngine huffman;
    huffman.buildTree(message);
    huffman.printCodebook();

    std::string encodedBits = huffman.encode(message);
    std::cout << "Original Size: " << (message.size() * 8) << " bits (" << message.size() << " bytes)\n";
    std::cout << "Encoded Size : " << encodedBits.size() << " bits\n";
    std::cout << "Compression  : " << std::fixed << std::setprecision(1)
              << (100.0 * (1.0 - static_cast<double>(encodedBits.size()) / (message.size() * 8))) << "% reduction\n";

    std::string decoded = huffman.decode(encodedBits);
    std::cout << "Decoded Match: " << (decoded == message ? "VERIFIED SUCCESS" : "MISMATCH") << "\n";

    std::cout << "\nTree Metrics: Depth = " << huffman.getDepth()
              << " | Unique Alphabet Count = " << huffman.getUniqueCharCount() << "\n";

    auto packed = huffman.packBitsToBytes(encodedBits);
    std::cout << "Raw Packed Bytes: " << packed.size() << " bytes (Down from " << message.size() << " bytes)\n";

    std::string unpackedBits = huffman.unpackBytesToBits(packed, encodedBits.size());
    std::cout << "Bitstream Integrity: " << (unpackedBits == encodedBits ? "PERFECT" : "CORRUPTED") << "\n";

    return 0;
}
