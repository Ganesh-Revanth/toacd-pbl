import java.util.*;

interface AstNode {
    double evaluate(Map<String, Double> env);
    String render(int depth);
}

class NumberNode implements AstNode {
    private final double value;

    public NumberNode(double value) { this.value = value; }

    @Override
    public double evaluate(Map<String, Double> env) { return value; }

    @Override
    public String render(int depth) {
        return "  ".repeat(depth) + "Number(" + value + ")\n";
    }
}

class VariableNode implements AstNode {
    private final String name;

    public VariableNode(String name) { this.name = name; }

    @Override
    public double evaluate(Map<String, Double> env) {
        if (!env.containsKey(name)) {
            throw new IllegalArgumentException("Variable not in environment: " + name);
        }
        return env.get(name);
    }

    @Override
    public String render(int depth) {
        return "  ".repeat(depth) + "Variable('" + name + "')\n";
    }
}

class BinaryOpNode implements AstNode {
    private final char operator;
    private AstNode left;
    private AstNode right;

    public BinaryOpNode(char op, AstNode left, AstNode right) {
        this.operator = op;
        this.left = left;
        this.right = right;
    }

    @Override
    public double evaluate(Map<String, Double> env) {
        double l = left.evaluate(env);
        double r = right.evaluate(env);
        switch (operator) {
            case '+': return l + r;
            case '-': return l - r;
            case '*': return l * r;
            case '/': 
                if (r == 0.0) throw new ArithmeticException("Division by zero in AST");
                return l / r;
            default: throw new UnsupportedOperationException("Unknown operator: " + operator);
        }
    }

    @Override
    public String render(int depth) {
        StringBuilder sb = new StringBuilder();
        sb.append("  ".repeat(depth)).append("BinaryOp('").append(operator).append("')\n");
        sb.append(left.render(depth + 1));
        sb.append(right.render(depth + 1));
        return sb.toString();
    }

    public AstNode getLeft() { return left; }
    public AstNode getRight() { return right; }
    public void setLeft(AstNode l) { this.left = l; }
    public void setRight(AstNode r) { this.right = r; }
}


interface AstVisitor<T> {
    T visitNumber(NumberNode n);
    T visitVariable(VariableNode v);
    T visitBinaryOp(BinaryOpNode b);
}

class AstDepthCalculator implements AstVisitor<Integer> {
    @Override
    public Integer visitNumber(NumberNode n) { return 1; }
    @Override
    public Integer visitVariable(VariableNode v) { return 1; }
    @Override
    public Integer visitBinaryOp(BinaryOpNode b) {
        return 1 + Math.max(visitNode(b.getLeft()), visitNode(b.getRight()));
    }
    public int visitNode(AstNode node) {
        if (node instanceof NumberNode) return visitNumber((NumberNode) node);
        if (node instanceof VariableNode) return visitVariable((VariableNode) node);
        if (node instanceof BinaryOpNode) return visitBinaryOp((BinaryOpNode) node);
        return 0;
    }
}

class AstOptimizerPipeline {
    public AstNode constantFold(AstNode node) {
        if (node instanceof BinaryOpNode) {
            BinaryOpNode bop = (BinaryOpNode) node;
            bop.setLeft(constantFold(bop.getLeft()));
            bop.setRight(constantFold(bop.getRight()));
            if (bop.getLeft() instanceof NumberNode && bop.getRight() instanceof NumberNode) {
                try {
                    double val = bop.evaluate(Collections.emptyMap());
                    return new NumberNode(val);
                } catch (Exception ignored) {}
            }
        }
        return node;
    }
}

public class Tc03JavaExpressionAst {
    public static void runAstHeader() {
        System.out.println("============================================================");
        System.out.println("   JAVA 17 ABSTRACT SYNTAX TREE (AST) PARSER ENGINE         ");
        System.out.println("   Recursive Tree Evaluation, Visitor & Constant Folding   ");
        System.out.println("============================================================");
        for (int k = 0; k < 20; ++k) {
            System.out.println("  [AST-NODE-SLOT-" + k + "] Initializing grammar evaluation slot " + k);
        }
    }

    public static void main(String[] args) {
        runAstHeader();

        // (x * 3.0) + (100.0 / 4.0)
        BinaryOpNode tree = new BinaryOpNode(
            '+',
            new BinaryOpNode('*', new VariableNode("x"), new NumberNode(3.0)),
            new BinaryOpNode('/', new NumberNode(100.0), new NumberNode(4.0))
        );

        System.out.println("Original AST Structure:");
        System.out.print(tree.render(0));

        AstOptimizerPipeline optimizer = new AstOptimizerPipeline();
        AstNode optimized = optimizer.constantFold(tree);

        System.out.println("\nOptimized AST Structure (Folded):");
        System.out.print(optimized.render(0));

        Map<String, Double> env = new HashMap<>();
        env.put("x", 15.0);

        double result = optimized.evaluate(env);
        System.out.println("Evaluated with x=15.0 -> Result = " + result);
    }
}
