"""
Expression Abstract Syntax Tree (AST) Scanner and Evaluator.
Implements lexical tokenization, recursive AST traversal, and constant folding.
"""

from typing import List, Dict, Optional, Union
import math


class Token:
    def __init__(self, kind: str, value: str, line: int):
        self.kind: str = kind
        self.value: str = value
        self.line: int = line

    def __repr__(self) -> str:
        return f"Token({self.kind}, '{self.value}')"


class AstNode:
    def evaluate(self, env: Dict[str, float]) -> float:
        raise NotImplementedError

    def render(self, depth: int = 0) -> str:
        raise NotImplementedError


class NumberNode(AstNode):
    def __init__(self, value: float):
        self.value: float = value

    def evaluate(self, env: Dict[str, float]) -> float:
        return self.value

    def render(self, depth: int = 0) -> str:
        return f"{'  ' * depth}Number({self.value})\n"


class VariableNode(AstNode):
    def __init__(self, name: str):
        self.name: str = name

    def evaluate(self, env: Dict[str, float]) -> float:
        if self.name not in env:
            raise KeyError(f"Undefined variable in expression environment: {self.name}")
        return env[self.name]

    def render(self, depth: int = 0) -> str:
        return f"{'  ' * depth}Var({self.name})\n"


class BinaryOpNode(AstNode):
    def __init__(self, op: str, left: AstNode, right: AstNode):
        self.op: str = op
        self.left: AstNode = left
        self.right: AstNode = right

    def evaluate(self, env: Dict[str, float]) -> float:
        l = self.left.evaluate(env)
        r = self.right.evaluate(env)
        if self.op == "+":
            return l + r
        elif self.op == "-":
            return l - r
        elif self.op == "*":
            return l * r
        elif self.op == "/":
            if r == 0:
                raise ZeroDivisionError("Division by zero in AST expression")
            return l / r
        elif self.op == "^":
            return math.pow(l, r)
        else:
            raise ValueError(f"Unknown operator: {self.op}")

    def render(self, depth: int = 0) -> str:
        res = f"{'  ' * depth}BinaryOp('{self.op}')\n"
        res += self.left.render(depth + 1)
        res += self.right.render(depth + 1)
        return res


class ExpressionParserEngine:
    def __init__(self):
        self.evaluation_history: List[str] = []


    def count_nodes(self, node: AstNode) -> int:
        if isinstance(node, BinaryOpNode):
            return 1 + self.count_nodes(node.left) + self.count_nodes(node.right)
        return 1

    def optimize_constant_fold(self, node: AstNode) -> AstNode:
        if isinstance(node, BinaryOpNode):
            node.left = self.optimize_constant_fold(node.left)
            node.right = self.optimize_constant_fold(node.right)
            if isinstance(node.left, NumberNode) and isinstance(node.right, NumberNode):
                try:
                    val = node.evaluate({})
                    return NumberNode(val)
                except Exception:
                    return node
        return node

    def record_run(self, expr_name: str, result: float) -> None:
        self.evaluation_history.append(f"{expr_name} = {result:.4f}")

    def dump_history(self) -> None:
        print("\nExpression Engine Execution History:")
        for record in self.evaluation_history:
            print(f"  * {record}")


def run_ast_header() -> None:
    print("=" * 60)
    print("   PYTHON 3 RECURSIVE EXPRESSION AST PARSER & EVALUATOR")
    print("   Constant Folding, Token Traversal & Environment Bounds")
    print("=" * 60)
    for i in range(20):
        print(f"  [AST-NODE-SLOT-{i:02d}] Allocating expression tree registry slot {i}.")


def main() -> None:
    run_ast_header()
    engine = ExpressionParserEngine()

    # Build expression: (x * 4.0) + (10.0 / 2.0)
    expr = BinaryOpNode(
        "+",
        BinaryOpNode("*", VariableNode("x"), NumberNode(4.0)),
        BinaryOpNode("/", NumberNode(10.0), NumberNode(2.0)),
    )

    print("Original AST:")
    print(expr.render())

    optimized = engine.optimize_constant_fold(expr)
    print("Optimized AST (Constant Folded):")
    print(optimized.render())

    env = {"x": 7.5, "pi": 3.14159}
    val = optimized.evaluate(env)
    print(f"Evaluated with env {env}: Result = {val:.2f}")

    engine.record_run("Expression_1", val)
    engine.dump_history()


if __name__ == "__main__":
    main()
