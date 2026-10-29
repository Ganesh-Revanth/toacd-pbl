"""
ir.py
-----
Three-Address Code (TAC) Intermediate Representation generation from MiniC AST.

Instructions represent operations with at most three addresses (result, arg1, arg2)
or control flow primitives (LABEL, JUMP, CALL, RETURN, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Union

from core.ast_nodes import (
    ASTNode,
    Assign,
    BinaryOp,
    Block,
    Call,
    ExprStmt,
    FunctionDef,
    Identifier,
    If,
    Literal,
    Print,
    Program,
    Return,
    UnaryOp,
    VarDecl,
    While,
)
from core.lexer import Lexer
from core.parser import Parser


# ── TAC Values & Instructions ─────────────────────────────────────────────────

@dataclass(frozen=True)
class Const:
    """Represents a literal constant in TAC (int, float, bool, or str)."""
    value: Any

    def __str__(self) -> str:
        if isinstance(self.value, str):
            return f'"{self.value}"'
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        return str(self.value)

    def __repr__(self) -> str:
        return f"Const({self.value!r})"


Operand = Union[str, Const]


@dataclass
class Instruction:
    """
    Three-Address Code (TAC) Quadruple instruction.
    Format: op, result, arg1, arg2
    """
    op: str
    result: Optional[str] = None
    arg1: Optional[Operand] = None
    arg2: Optional[Operand] = None

    def __str__(self) -> str:
        if self.op == "LABEL":
            return f"{self.arg1}:"
        if self.op == "FUNC_BEGIN":
            params = f" ({', '.join(self.arg2)})" if self.arg2 else ""
            return f"func begin {self.arg1}{params}"
        if self.op == "FUNC_END":
            return f"func end {self.arg1}"
        if self.op == "ASSIGN":
            return f"{self.result} = {self.arg1}"
        if self.op in ("+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"):
            return f"{self.result} = {self.arg1} {self.op} {self.arg2}"
        if self.op in ("!", "-u", "+u"):
            op_sym = "!" if self.op == "!" else ("-" if self.op == "-u" else "+")
            return f"{self.result} = {op_sym}{self.arg1}"
        if self.op == "JUMP":
            return f"goto {self.arg1}"
        if self.op == "JUMP_IF_FALSE":
            return f"if_false {self.arg1} goto {self.arg2}"
        if self.op == "JUMP_IF":
            return f"if {self.arg1} goto {self.arg2}"
        if self.op == "PARAM":
            return f"param {self.arg1}"
        if self.op == "CALL":
            res_str = f"{self.result} = " if self.result else ""
            return f"{res_str}call {self.arg1}, {self.arg2}"
        if self.op == "RETURN":
            return f"return {self.arg1}" if self.arg1 is not None else "return"
        if self.op == "PRINT":
            return f"print {self.arg1}"
        if self.op == "HALT":
            return "halt"

        return f"{self.op} {self.result} {self.arg1} {self.arg2}".strip()


# ── TAC Generator ─────────────────────────────────────────────────────────────

class IRGenerator:
    """
    Converts a MiniC AST into Three-Address Code (TAC) instructions.
    """

    def __init__(self) -> None:
        self.instructions: List[Instruction] = []
        self.temp_counter: int = 0
        self.label_counter: int = 0

    def new_temp(self) -> str:
        """Allocate a unique temporary variable name."""
        t = f"t{self.temp_counter}"
        self.temp_counter += 1
        return t

    def new_label(self, prefix: str = "L") -> str:
        """Allocate a unique jump label name."""
        lbl = f"{prefix}_{self.label_counter}"
        self.label_counter += 1
        return lbl

    def emit(
        self,
        op: str,
        result: Optional[str] = None,
        arg1: Optional[Operand] = None,
        arg2: Optional[Operand] = None,
    ) -> Instruction:
        """Create and append an instruction to the TAC stream."""
        inst = Instruction(op=op, result=result, arg1=arg1, arg2=arg2)
        self.instructions.append(inst)
        return inst

    def generate(self, program: Program) -> List[Instruction]:
        """Main entry point: generate TAC for an entire Program AST."""
        self.instructions.clear()

        has_main = False
        functions: List[FunctionDef] = []
        top_level_stmts: List[ASTNode] = []

        for decl in program.declarations:
            if isinstance(decl, FunctionDef):
                functions.append(decl)
                if decl.name == "main":
                    has_main = True
            else:
                top_level_stmts.append(decl)

        if has_main:
            # Emit top-level initialization statements
            for stmt in top_level_stmts:
                self.visit(stmt)

            # Call main and halt
            main_temp = self.new_temp()
            self.emit("CALL", result=main_temp, arg1="main", arg2=0)
            self.emit("HALT")

            # Emit all function bodies
            for func in functions:
                self.visit_FunctionDef(func)
        else:
            # Script-style execution without a main function
            for decl in program.declarations:
                self.visit(decl)
            self.emit("HALT")

        return self.instructions

    # ── Visitor Dispatch ──────────────────────────────────────────────────────

    def visit(self, node: Optional[ASTNode]) -> Optional[Operand]:
        if node is None:
            return None
        method = getattr(self, f"visit_{node.__class__.__name__}", None)
        if method is None:
            raise NotImplementedError(f"No IR generator visitor for {node.__class__.__name__}")
        return method(node)

    # ── Functions & Blocks ────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        param_names = [p[1] for p in node.params]
        self.emit("FUNC_BEGIN", arg1=node.name, arg2=param_names)

        if node.body:
            for stmt in node.body.statements:
                self.visit(stmt)

        # Safety return for void functions
        self.emit("RETURN")
        self.emit("FUNC_END", arg1=node.name)

    def visit_Block(self, node: Block) -> None:
        for stmt in node.statements:
            self.visit(stmt)

    # ── Statements ────────────────────────────────────────────────────────────

    def visit_VarDecl(self, node: VarDecl) -> None:
        if node.initializer is not None:
            val = self.visit(node.initializer)
            self.emit("ASSIGN", result=node.name, arg1=val)

    def visit_Assign(self, node: Assign) -> None:
        val = self.visit(node.value)
        self.emit("ASSIGN", result=node.target, arg1=val)

    def visit_If(self, node: If) -> None:
        cond = self.visit(node.condition)
        lbl_else = self.new_label("L_else")
        lbl_end = self.new_label("L_end_if")

        if node.else_branch is not None:
            self.emit("JUMP_IF_FALSE", arg1=cond, arg2=lbl_else)
            self.visit(node.then_branch)
            self.emit("JUMP", arg1=lbl_end)
            self.emit("LABEL", arg1=lbl_else)
            self.visit(node.else_branch)
            self.emit("LABEL", arg1=lbl_end)
        else:
            self.emit("JUMP_IF_FALSE", arg1=cond, arg2=lbl_end)
            self.visit(node.then_branch)
            self.emit("LABEL", arg1=lbl_end)

    def visit_While(self, node: While) -> None:
        lbl_start = self.new_label("L_loop_start")
        lbl_end = self.new_label("L_loop_end")

        self.emit("LABEL", arg1=lbl_start)
        cond = self.visit(node.condition)
        self.emit("JUMP_IF_FALSE", arg1=cond, arg2=lbl_end)
        self.visit(node.body)
        self.emit("JUMP", arg1=lbl_start)
        self.emit("LABEL", arg1=lbl_end)

    def visit_Return(self, node: Return) -> None:
        if node.value is not None:
            val = self.visit(node.value)
            self.emit("RETURN", arg1=val)
        else:
            self.emit("RETURN")

    def visit_Print(self, node: Print) -> None:
        val = self.visit(node.expression)
        self.emit("PRINT", arg1=val)

    def visit_ExprStmt(self, node: ExprStmt) -> None:
        self.visit(node.expr)

    # ── Expressions ───────────────────────────────────────────────────────────

    def visit_Literal(self, node: Literal) -> Operand:
        return Const(node.value)

    def visit_Identifier(self, node: Identifier) -> Operand:
        return node.name

    def visit_BinaryOp(self, node: BinaryOp) -> Operand:
        left = self.visit(node.left)
        right = self.visit(node.right)
        t = self.new_temp()
        self.emit(node.operator, result=t, arg1=left, arg2=right)
        return t

    def visit_UnaryOp(self, node: UnaryOp) -> Operand:
        operand = self.visit(node.operand)
        t = self.new_temp()
        op_code = "-u" if node.operator == "-" else ("+u" if node.operator == "+" else "!")
        self.emit(op_code, result=t, arg1=operand)
        return t

    def visit_Call(self, node: Call) -> Operand:
        arg_ops = [self.visit(arg) for arg in node.args]
        for arg in arg_ops:
            self.emit("PARAM", arg1=arg)
        t = self.new_temp()
        self.emit("CALL", result=t, arg1=node.callee, arg2=len(node.args))
        return t


# ── Top-Level API ─────────────────────────────────────────────────────────────

def generate_ir(ast_or_source: Union[ASTNode, str]) -> List[Instruction]:
    """
    Generate Three-Address Code (TAC) from a MiniC source string or AST.
    """
    if isinstance(ast_or_source, str):
        lexer = Lexer(ast_or_source)
        tokens = lexer.tokenize()
        if lexer.errors:
            raise SyntaxError(f"Lexer errors: {lexer.errors}")
        parser = Parser(tokens)
        ast = parser.parse()
        if parser.errors:
            raise SyntaxError(f"Parser errors: {parser.errors}")
    else:
        ast = ast_or_source

    if not isinstance(ast, Program):
        raise TypeError(f"Expected Program AST node, got {type(ast).__name__}")

    gen = IRGenerator()
    return gen.generate(ast)
