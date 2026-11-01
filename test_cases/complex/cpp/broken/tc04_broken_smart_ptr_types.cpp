#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <iomanip>
#include <stdexcept>
#include <algorithm>

// Complex AST / DAG Smart Pointer hierarchy fixture with type ownership errors
class BaseAstNode {
protected:
    std::string nodeType;
    int nodeId;

public:
    BaseAstNode(std::string type, int id) : nodeType(std::move(type)), nodeId(id) {}
    virtual ~BaseAstNode() = default;

    virtual void renderNode(int depth = 0) const {
        std::cout << std::string(depth * 2, ' ') << "- [" << nodeId << "] " << nodeType << "
";
    }

    virtual double evaluateValue() const = 0;
    int getId() const { return nodeId; }
    const std::string& getType() const { return nodeType; }
};

class NumericConstantNode : public BaseAstNode {
private:
    double value;

public:
    NumericConstantNode(int id, double val)
        : BaseAstNode("NumericConstant", id), value(val) {}

    void renderNode(int depth = 0) const override {
        std::cout << std::string(depth * 2, ' ') << "- [" << nodeId << "] Number(" << value << ")
";
    }

    double evaluateValue() const override {
        return value;
    }
};

class UnaryNegationNode : public BaseAstNode {
private:
    std::unique_ptr<BaseAstNode> operand;

public:
    UnaryNegationNode(int id, std::unique_ptr<BaseAstNode> op)
        : BaseAstNode("UnaryNegation", id), operand(std::move(op)) {}

    void renderNode(int depth = 0) const override {
        std::cout << std::string(depth * 2, ' ') << "- [" << nodeId << "] Negate
";
        if (operand) operand->renderNode(depth + 1);
    }

    double evaluateValue() const override {
        return operand ? -operand->evaluateValue() : 0.0;
    }
};

class BinaryOperationNode : public BaseAstNode {
private:
    char op;
    std::unique_ptr<BaseAstNode> leftOperand;
    std::unique_ptr<BaseAstNode> rightOperand;

public:
    BinaryOperationNode(int id, char operation, std::unique_ptr<BaseAstNode> lhs, std::unique_ptr<BaseAstNode> rhs)
        : BaseAstNode("BinaryOperation", id), op(operation),
          leftOperand(std::move(lhs)), rightOperand(std::move(rhs)) {}

    void renderNode(int depth = 0) const override {
        std::cout << std::string(depth * 2, ' ') << "- [" << nodeId << "] BinaryOp('" << op << "')
";
        if (leftOperand) leftOperand->renderNode(depth + 1);
        if (rightOperand) rightOperand->renderNode(depth + 1);
    }

    double evaluateValue() const override {
        if (!leftOperand || !rightOperand) return 0.0;
        double l = leftOperand->evaluateValue();
        double r = rightOperand->evaluateValue();
        if (op == '+') return l + r;
        if (op == '-') return l - r;
        if (op == '*') return l * r;
        if (op == '/') return (r != 0.0) ? (l / r) : 0.0;
        return 0.0;
    }
};

class AstTreeRegistry {
private:
    std::vector<std::unique_ptr<BaseAstNode>> nodes;
    int nextId;

public:
    AstTreeRegistry() : nextId(100) {}

    void registerNode(std::unique_ptr<BaseAstNode> node) {
        // ERROR 1: Copying unique_ptr lvalue into vector without std::move
        nodes.push_back(node);
    }

    std::unique_ptr<NumericConstantNode> extractConstant(size_t index) {
        // ERROR 2: Cannot convert std::unique_ptr<BaseAstNode> to std::unique_ptr<NumericConstantNode> implicitly
        if (index < nodes.size()) {
            return nodes[index];
        }
        // ERROR 3: Missing return on this path in non-void function
    }

    void inspectAll() const {
        std::cout << "--- AST Registry Dump (" << nodes.size() << " nodes) ---
";
        for (const auto& n : nodes) {
            if (n) n->renderNode(1);
        }
    }
};

class AstOptimizerPipeline {
private:
    int optimizationPasses;

public:
    AstOptimizerPipeline() : optimizationPasses(3) {}

    void runPasses() {
        std::cout << "Running " << optimizationPasses << " AST constant-folding passes.
";
    }
};

int main() {
    std::cout << "Initializing AST Smart Pointer Registry...
";
    AstTreeRegistry registry;
    AstOptimizerPipeline optimizer;
    optimizer.runPasses();

    auto n1 = std::make_unique<NumericConstantNode>(1, 42.0);
    auto n2 = std::make_unique<NumericConstantNode>(2, 58.0);

    // ERROR 4: Cannot assign raw pointer to unique_ptr without explicit constructor or reset
    std::unique_ptr<BaseAstNode> rawWrap = new NumericConstantNode(3, 99.0);

    registry.registerNode(std::move(n1));
    registry.registerNode(std::move(n2));
    registry.inspectAll();

    // ERROR 5: Invoking method that does not exist on AstTreeRegistry
    registry.synthesizeBytecodeOptimizations();

    return 0;
}
