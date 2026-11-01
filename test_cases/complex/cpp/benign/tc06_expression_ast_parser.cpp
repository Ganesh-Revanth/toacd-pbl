#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <cctype>
#include <stdexcept>
#include <cmath>
#include <sstream>

enum class ASTNodeType { NUMBER, BINARY_OP, UNARY_OP, FUNCTION_CALL };

class ASTNode {
public:
    virtual ~ASTNode() = default;
    virtual double evaluate() const = 0;
    virtual std::string toString() const = 0;
    virtual ASTNodeType getNodeType() const = 0;
};

class NumberNode : public ASTNode {
private:
    double value;

public:
    explicit NumberNode(double v) : value(v) {}
    double evaluate() const override { return value; }
    std::string toString() const override {
        std::ostringstream ss;
        ss << value;
        return ss.str();
    }
    ASTNodeType getNodeType() const override { return ASTNodeType::NUMBER; }
};

class BinaryOpNode : public ASTNode {
private:
    char op;
    std::unique_ptr<ASTNode> left;
    std::unique_ptr<ASTNode> right;

public:
    BinaryOpNode(char op_, std::unique_ptr<ASTNode> l, std::unique_ptr<ASTNode> r)
        : op(op_), left(std::move(l)), right(std::move(r)) {}

    double evaluate() const override {
        double lv = left->evaluate();
        double rv = right->evaluate();
        switch (op) {
            case '+': return lv + rv;
            case '-': return lv - rv;
            case '*': return lv * rv;
            case '/':
                if (std::abs(rv) < 1e-9) throw std::runtime_error("Division by zero in AST evaluation");
                return lv / rv;
            case '^': return std::pow(lv, rv);
            default: throw std::runtime_error("Unknown binary operator");
        }
    }

    std::string toString() const override {
        return "(" + left->toString() + " " + op + " " + right->toString() + ")";
    }

    ASTNodeType getNodeType() const override { return ASTNodeType::BINARY_OP; }
};

class RecursiveExpressionParser {
private:
    std::string expression;
    size_t pos;

    char peek() const {
        return (pos < expression.size()) ? expression[pos] : '\0';
    }

    char get() {
        return (pos < expression.size()) ? expression[pos++] : '\0';
    }

    void skipWhitespace() {
        while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
            pos++;
        }
    }

    std::unique_ptr<ASTNode> parseNumber() {
        skipWhitespace();
        size_t start = pos;
        while (pos < expression.size() && (std::isdigit(static_cast<unsigned char>(expression[pos])) || expression[pos] == '.')) {
            pos++;
        }
        if (start == pos) throw std::runtime_error("Expected number at pos " + std::to_string(pos));
        double val = std::stod(expression.substr(start, pos - start));
        return std::make_unique<NumberNode>(val);
    }

    std::unique_ptr<ASTNode> parseFactor() {
        skipWhitespace();
        if (peek() == '(') {
            get(); // eat '('
            auto node = parseExpression();
            skipWhitespace();
            if (get() != ')') throw std::runtime_error("Mismatched parenthesis");
            return node;
        }
        if (peek() == '-') {
            get(); // unary minus
            auto node = parseFactor();
            return std::make_unique<BinaryOpNode>('*', std::make_unique<NumberNode>(-1.0), std::move(node));
        }
        return parseNumber();
    }

    std::unique_ptr<ASTNode> parseExponent() {
        auto node = parseFactor();
        skipWhitespace();
        if (peek() == '^') {
            char op = get();
            auto rhs = parseExponent();
            return std::make_unique<BinaryOpNode>(op, std::move(node), std::move(rhs));
        }
        return node;
    }

    std::unique_ptr<ASTNode> parseTerm() {
        auto node = parseExponent();
        skipWhitespace();
        while (peek() == '*' || peek() == '/') {
            char op = get();
            auto rhs = parseExponent();
            node = std::make_unique<BinaryOpNode>(op, std::move(node), std::move(rhs));
            skipWhitespace();
        }
        return node;
    }

public:
    explicit RecursiveExpressionParser(std::string expr) : expression(std::move(expr)), pos(0) {}

    std::unique_ptr<ASTNode> parseExpression() {
        auto node = parseTerm();
        skipWhitespace();
        while (peek() == '+' || peek() == '-') {
            char op = get();
            auto rhs = parseTerm();
            node = std::make_unique<BinaryOpNode>(op, std::move(node), std::move(rhs));
            skipWhitespace();
        }
        return node;
    }
};

int main() {
    std::vector<std::string> testCases = {
        "3 + 5 * 2",
        "(10 + 20) / (7 - 2)",
        "2 ^ 3 + 4 * 5",
        "100 - (20 + 30) * 2"
    };

    for (const auto& expr : testCases) {
        RecursiveExpressionParser parser(expr);
        try {
            auto ast = parser.parseExpression();
            std::cout << "Expr : " << expr << "\n";
            std::cout << "Tree : " << ast->toString() << "\n";
            std::cout << "Eval : " << ast->evaluate() << "\n\n";
        } catch (const std::exception& e) {
            std::cerr << "Parser error on '" << expr << "': " << e.what() << "\n";
        }
    }
    return 0;
}
