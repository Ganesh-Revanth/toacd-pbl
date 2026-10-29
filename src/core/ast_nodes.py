"""
ast_nodes.py
------------
Abstract Syntax Tree (AST) node definitions and pretty-printer for MiniC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass
class ASTNode:
    """Base class for all AST nodes with source position tracking."""
    line: int = 0
    column: int = 0


# ── Top-Level Program & Functions ─────────────────────────────────────────────

@dataclass
class Program(ASTNode):
    declarations: List[ASTNode] = field(default_factory=list)


@dataclass
class FunctionDef(ASTNode):
    return_type: str = "void"
    name: str = ""
    params: List[Tuple[str, str]] = field(default_factory=list)  # [(type, name), ...]
    body: Block = field(default_factory=lambda: Block())


@dataclass
class Block(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)


# ── Statements ────────────────────────────────────────────────────────────────

@dataclass
class VarDecl(ASTNode):
    var_type: str = "int"
    name: str = ""
    initializer: Optional[ASTNode] = None


@dataclass
class Assign(ASTNode):
    target: str = ""
    value: Optional[ASTNode] = None


@dataclass
class If(ASTNode):
    condition: Optional[ASTNode] = None
    then_branch: Optional[ASTNode] = None
    else_branch: Optional[ASTNode] = None


@dataclass
class While(ASTNode):
    condition: Optional[ASTNode] = None
    body: Optional[ASTNode] = None


@dataclass
class Return(ASTNode):
    value: Optional[ASTNode] = None


@dataclass
class Print(ASTNode):
    expression: Optional[ASTNode] = None


@dataclass
class ExprStmt(ASTNode):
    expr: Optional[ASTNode] = None


# ── Expressions ───────────────────────────────────────────────────────────────

@dataclass
class BinaryOp(ASTNode):
    left: Optional[ASTNode] = None
    operator: str = ""
    right: Optional[ASTNode] = None


@dataclass
class UnaryOp(ASTNode):
    operator: str = ""
    operand: Optional[ASTNode] = None


@dataclass
class Call(ASTNode):
    callee: str = ""
    args: List[ASTNode] = field(default_factory=list)


@dataclass
class Literal(ASTNode):
    value: Any = None
    literal_type: str = "int"


@dataclass
class Identifier(ASTNode):
    name: str = ""


# ── AST Pretty-Printer ────────────────────────────────────────────────────────

def pretty_print_ast(node: Optional[ASTNode], indent: int = 0) -> str:
    """
    Produce an indented, human-readable tree representation of an AST.
    """
    if node is None:
        return " " * indent + "<None>\n"

    prefix = " " * indent
    lines: List[str] = []

    if isinstance(node, Program):
        lines.append(f"{prefix}Program (lines={len(node.declarations)} decls):")
        for decl in node.declarations:
            lines.append(pretty_print_ast(decl, indent + 2))

    elif isinstance(node, FunctionDef):
        param_str = ", ".join(f"{t} {n}" for t, n in node.params)
        lines.append(f"{prefix}FunctionDef: {node.return_type} {node.name}({param_str}) [L{node.line}:{node.column}]")
        lines.append(pretty_print_ast(node.body, indent + 2))

    elif isinstance(node, Block):
        lines.append(f"{prefix}Block ({len(node.statements)} stmts):")
        for s in node.statements:
            lines.append(pretty_print_ast(s, indent + 2))

    elif isinstance(node, VarDecl):
        init_str = " (with initializer)" if node.initializer else ""
        lines.append(f"{prefix}VarDecl: {node.var_type} {node.name}{init_str} [L{node.line}:{node.column}]")
        if node.initializer:
            lines.append(pretty_print_ast(node.initializer, indent + 2))

    elif isinstance(node, Assign):
        lines.append(f"{prefix}Assign: {node.target} = [L{node.line}:{node.column}]")
        lines.append(pretty_print_ast(node.value, indent + 2))

    elif isinstance(node, If):
        has_else = " + else" if node.else_branch else ""
        lines.append(f"{prefix}If{has_else} [L{node.line}:{node.column}]:")
        lines.append(f"{prefix}  Condition:")
        lines.append(pretty_print_ast(node.condition, indent + 4))
        lines.append(f"{prefix}  Then:")
        lines.append(pretty_print_ast(node.then_branch, indent + 4))
        if node.else_branch:
            lines.append(f"{prefix}  Else:")
            lines.append(pretty_print_ast(node.else_branch, indent + 4))

    elif isinstance(node, While):
        lines.append(f"{prefix}While [L{node.line}:{node.column}]:")
        lines.append(f"{prefix}  Condition:")
        lines.append(pretty_print_ast(node.condition, indent + 4))
        lines.append(f"{prefix}  Body:")
        lines.append(pretty_print_ast(node.body, indent + 4))

    elif isinstance(node, Return):
        val_str = " (void)" if node.value is None else ""
        lines.append(f"{prefix}Return{val_str} [L{node.line}:{node.column}]")
        if node.value:
            lines.append(pretty_print_ast(node.value, indent + 2))

    elif isinstance(node, Print):
        lines.append(f"{prefix}Print [L{node.line}:{node.column}]:")
        lines.append(pretty_print_ast(node.expression, indent + 2))

    elif isinstance(node, ExprStmt):
        lines.append(f"{prefix}ExprStmt [L{node.line}:{node.column}]:")
        lines.append(pretty_print_ast(node.expr, indent + 2))

    elif isinstance(node, BinaryOp):
        lines.append(f"{prefix}BinaryOp ('{node.operator}') [L{node.line}:{node.column}]:")
        lines.append(pretty_print_ast(node.left, indent + 2))
        lines.append(pretty_print_ast(node.right, indent + 2))

    elif isinstance(node, UnaryOp):
        lines.append(f"{prefix}UnaryOp ('{node.operator}') [L{node.line}:{node.column}]:")
        lines.append(pretty_print_ast(node.operand, indent + 2))

    elif isinstance(node, Call):
        lines.append(f"{prefix}Call: {node.callee}({len(node.args)} args) [L{node.line}:{node.column}]:")
        for arg in node.args:
            lines.append(pretty_print_ast(arg, indent + 2))

    elif isinstance(node, Literal):
        lines.append(f"{prefix}Literal: {node.value!r} ({node.literal_type}) [L{node.line}:{node.column}]\n")
        return "".join(lines)

    elif isinstance(node, Identifier):
        lines.append(f"{prefix}Identifier: {node.name} [L{node.line}:{node.column}]\n")
        return "".join(lines)

    else:
        lines.append(f"{prefix}{node.__class__.__name__} [L{node.line}:{node.column}]\n")
        return "".join(lines)

    return "".join(lines)
