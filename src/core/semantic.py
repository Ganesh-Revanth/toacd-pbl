"""
semantic.py
-----------
Scoped symbol table and semantic analyzer (AST visitor) for MiniC.

Checks performed:
  1. Undeclared variables and functions.
  2. Redeclaration of variables, parameters, or functions in the same scope.
  3. Type mismatches in assignments, initializations, and binary/unary operations.
  4. Wrong argument count or argument types in function calls.
  5. Missing return statements in non-void functions & return type mismatches.
  6. Use of variables before initialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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


# ── Diagnostics ───────────────────────────────────────────────────────────────

@dataclass
class Diagnostic:
    """Represents a compile-time semantic diagnostic (error/warning)."""
    message: str
    line: int
    column: int
    severity: str = "error"

    def __str__(self) -> str:
        return f"[Line {self.line}:{self.column}] Semantic {self.severity.capitalize()}: {self.message}"


# ── Symbols & Symbol Table ────────────────────────────────────────────────────

@dataclass
class Symbol:
    """Base class for named entities in the symbol table."""
    name: str
    line: int = 0
    column: int = 0


@dataclass
class VarSymbol(Symbol):
    """Represents a variable or parameter symbol."""
    var_type: str = "int"
    is_param: bool = False

    def __hash__(self) -> int:
        return id(self)


@dataclass
class FuncSymbol(Symbol):
    """Represents a function symbol with signature."""
    return_type: str = "void"
    params: List[Tuple[str, str]] = field(default_factory=list)  # [(type, name), ...]


class SymbolTable:
    """
    Scoped symbol table supporting hierarchical lookup and current-scope definition.
    """

    def __init__(self, parent: Optional["SymbolTable"] = None, name: str = "scope") -> None:
        self.parent = parent
        self.name = name
        self.symbols: Dict[str, Symbol] = {}

    def define(self, symbol: Symbol) -> bool:
        """
        Define a symbol in the current scope.
        Returns False if the symbol name is already declared in this exact scope.
        """
        if symbol.name in self.symbols:
            return False
        self.symbols[symbol.name] = symbol
        return True

    def lookup(self, name: str) -> Optional[Symbol]:
        """
        Lookup a symbol recursively from the current scope outward to global scope.
        """
        if name in self.symbols:
            return self.symbols[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        return None

    def lookup_current(self, name: str) -> Optional[Symbol]:
        """
        Lookup a symbol only within the current immediate scope.
        """
        return self.symbols.get(name)


# ── Control Flow Analysis Helpers ─────────────────────────────────────────────

def guarantees_return(stmt: Optional[ASTNode]) -> bool:
    """
    Check if a statement or block guarantees execution of a return statement
    along all control flow paths.
    """
    if stmt is None:
        return False

    if isinstance(stmt, Return):
        return True

    if isinstance(stmt, Block):
        for s in stmt.statements:
            if guarantees_return(s):
                return True
        return False

    if isinstance(stmt, If):
        if stmt.else_branch is not None:
            return guarantees_return(stmt.then_branch) and guarantees_return(stmt.else_branch)
        return False

    return False


# ── AST Visitor Base Class ────────────────────────────────────────────────────

class ASTVisitor:
    """Generic AST visitor dispatching to visit_<ClassName>."""

    def visit(self, node: Optional[ASTNode], *args: Any, **kwargs: Any) -> Any:
        if node is None:
            return None
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node, *args, **kwargs)

    def generic_visit(self, node: ASTNode, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(f"No visitor method defined for {node.__class__.__name__}")


# ── Semantic Analyzer ─────────────────────────────────────────────────────────

class SemanticAnalyzer(ASTVisitor):
    """
    Performs type checking, scope validation, and flow checks on a MiniC AST.
    """

    NUMERIC_TYPES = {"int", "float"}
    ALL_TYPES = {"int", "float", "bool", "string", "void"}

    def __init__(self) -> None:
        self.diagnostics: List[Diagnostic] = []
        self.global_scope = SymbolTable(parent=None, name="global")
        self.current_scope = self.global_scope
        self.current_function: Optional[FuncSymbol] = None
        # Track initialized variable symbols (scoped object identity)
        self.initialized_symbols: Set[VarSymbol] = set()

    def error(self, node: ASTNode, message: str) -> None:
        """Record a semantic error diagnostic."""
        self.diagnostics.append(
            Diagnostic(message=message, line=node.line, column=node.column, severity="error")
        )

    def analyze(self, program: Program) -> List[Diagnostic]:
        """Entry point to analyze a complete Program AST."""
        self.visit(program)
        return self.diagnostics

    # ── Program & Declarations ────────────────────────────────────────────────

    def visit_Program(self, node: Program) -> None:
        # Pre-pass: register all function signatures in the global scope so forward calls work
        for decl in node.declarations:
            if isinstance(decl, FunctionDef):
                existing = self.global_scope.lookup_current(decl.name)
                if existing is not None:
                    self.error(decl, f"Redeclaration of function '{decl.name}'")
                else:
                    func_sym = FuncSymbol(
                        name=decl.name,
                        return_type=decl.return_type,
                        params=decl.params,
                        line=decl.line,
                        column=decl.column,
                    )
                    self.global_scope.define(func_sym)

        # Full analysis pass
        for decl in node.declarations:
            self.visit(decl)

    def visit_FunctionDef(self, node: FunctionDef) -> None:
        func_sym = self.global_scope.lookup(node.name)
        if not isinstance(func_sym, FuncSymbol):
            func_sym = FuncSymbol(
                name=node.name,
                return_type=node.return_type,
                params=node.params,
                line=node.line,
                column=node.column,
            )

        prev_function = self.current_function
        prev_scope = self.current_scope
        prev_inits = set(self.initialized_symbols)

        self.current_function = func_sym
        func_scope = SymbolTable(parent=self.current_scope, name=f"func_{node.name}")
        self.current_scope = func_scope

        # Register parameters in the function scope
        seen_params: Set[str] = set()
        for p_type, p_name in node.params:
            if p_name in seen_params:
                self.error(node, f"Redeclaration of parameter '{p_name}' in function '{node.name}'")
            else:
                seen_params.add(p_name)
                param_sym = VarSymbol(
                    name=p_name,
                    var_type=p_type,
                    line=node.line,
                    column=node.column,
                    is_param=True,
                )
                func_scope.define(param_sym)
                self.initialized_symbols.add(param_sym)

        # Visit body statements directly within the function scope (shares param scope)
        if node.body:
            for stmt in node.body.statements:
                self.visit(stmt)

        # Non-void functions must guarantee a return
        if node.return_type != "void":
            if not guarantees_return(node.body):
                self.error(node, f"Missing return statement in non-void function '{node.name}'")

        # Restore context
        self.current_function = prev_function
        self.current_scope = prev_scope
        self.initialized_symbols = prev_inits

    def visit_Block(self, node: Block) -> None:
        # Create a nested block scope (for inner blocks inside functions, if, while)
        block_scope = SymbolTable(parent=self.current_scope, name="block")
        prev_scope = self.current_scope
        self.current_scope = block_scope

        for stmt in node.statements:
            self.visit(stmt)

        self.current_scope = prev_scope

    # ── Statements ────────────────────────────────────────────────────────────

    def visit_VarDecl(self, node: VarDecl) -> None:
        # Check redeclaration in the current scope
        if self.current_scope.lookup_current(node.name) is not None:
            self.error(node, f"Redeclaration of variable '{node.name}' in the same scope")
            return

        var_sym = VarSymbol(
            name=node.name,
            var_type=node.var_type,
            line=node.line,
            column=node.column,
            is_param=False,
        )
        self.current_scope.define(var_sym)

        if node.initializer is not None:
            # Visit initializer BEFORE marking initialized to catch self-initialization (e.g. int x = x;)
            init_type = self.visit(node.initializer)
            if init_type is not None and init_type != "error":
                if init_type != node.var_type:
                    self.error(
                        node,
                        f"Cannot initialize variable '{node.name}' of type '{node.var_type}' "
                        f"with expression of type '{init_type}'",
                    )
            # Mark initialized
            self.initialized_symbols.add(var_sym)

    def visit_Assign(self, node: Assign) -> None:
        sym = self.current_scope.lookup(node.target)
        if sym is None:
            self.error(node, f"Undeclared variable '{node.target}'")
        elif not isinstance(sym, VarSymbol):
            self.error(node, f"Cannot assign to '{node.target}', which is a function")

        val_type = self.visit(node.value)

        if sym is not None and isinstance(sym, VarSymbol):
            if val_type is not None and val_type != "error":
                if sym.var_type != val_type:
                    self.error(
                        node,
                        f"Cannot assign type '{val_type}' to variable '{node.target}' of type '{sym.var_type}'",
                    )
            # Variable is now initialized
            self.initialized_symbols.add(sym)

    def visit_If(self, node: If) -> None:
        cond_type = self.visit(node.condition)
        if cond_type is not None and cond_type != "error" and cond_type != "bool":
            self.error(node, f"Condition expression in 'if' must be of type 'bool', got '{cond_type}'")

        # Definite assignment tracking across branches
        inits_before = set(self.initialized_symbols)

        # Then branch
        if isinstance(node.then_branch, Block):
            self.visit(node.then_branch)
        else:
            self.visit(node.then_branch)
        inits_then = set(self.initialized_symbols)

        if node.else_branch is not None:
            self.initialized_symbols = set(inits_before)
            if isinstance(node.else_branch, Block):
                self.visit(node.else_branch)
            else:
                self.visit(node.else_branch)
            inits_else = set(self.initialized_symbols)
            # Variable is initialized only if initialized in BOTH then and else branches
            self.initialized_symbols = inits_then.intersection(inits_else)
        else:
            # If without else cannot guarantee execution of then branch
            self.initialized_symbols = inits_before

    def visit_While(self, node: While) -> None:
        cond_type = self.visit(node.condition)
        if cond_type is not None and cond_type != "error" and cond_type != "bool":
            self.error(node, f"Condition expression in 'while' must be of type 'bool', got '{cond_type}'")

        inits_before = set(self.initialized_symbols)
        if isinstance(node.body, Block):
            self.visit(node.body)
        else:
            self.visit(node.body)
        # Loop body might execute 0 times, so inits inside while are not guaranteed after loop
        self.initialized_symbols = inits_before

    def visit_Return(self, node: Return) -> None:
        if self.current_function is None:
            self.error(node, "'return' statement outside of function")
            return

        expected_type = self.current_function.return_type

        if node.value is None:
            if expected_type != "void":
                self.error(
                    node,
                    f"Non-void function '{self.current_function.name}' must return a value of type '{expected_type}'",
                )
        else:
            val_type = self.visit(node.value)
            if expected_type == "void":
                self.error(
                    node,
                    f"Void function '{self.current_function.name}' cannot return a value",
                )
            elif val_type is not None and val_type != "error":
                if val_type != expected_type:
                    self.error(
                        node,
                        f"Function '{self.current_function.name}' expects return type '{expected_type}', got '{val_type}'",
                    )

    def visit_Print(self, node: Print) -> None:
        self.visit(node.expression)

    def visit_ExprStmt(self, node: ExprStmt) -> None:
        self.visit(node.expr)

    # ── Expressions & Type Inference ──────────────────────────────────────────

    def visit_Literal(self, node: Literal) -> str:
        return node.literal_type

    def visit_Identifier(self, node: Identifier) -> str:
        sym = self.current_scope.lookup(node.name)
        if sym is None:
            self.error(node, f"Undeclared variable '{node.name}'")
            return "error"

        if not isinstance(sym, VarSymbol):
            self.error(node, f"'{node.name}' is a function, not a variable")
            return "error"

        # Check use before initialization
        if not sym.is_param and sym not in self.initialized_symbols:
            self.error(node, f"Variable '{node.name}' used before initialization")
            # Mark initialized to prevent repeating identical error on every use
            self.initialized_symbols.add(sym)

        return sym.var_type

    def visit_BinaryOp(self, node: BinaryOp) -> str:
        t_left = self.visit(node.left)
        t_right = self.visit(node.right)

        if t_left == "error" or t_right == "error":
            return "error"

        op = node.operator

        # 1. Modulo operator (%) requires integers
        if op == "%":
            if t_left != "int" or t_right != "int":
                self.error(node, f"Operator '%' requires operands of type 'int', got '{t_left}' and '{t_right}'")
                return "error"
            return "int"

        # 2. Arithmetic operators (+, -, *, /)
        if op in ("+", "-", "*", "/"):
            if t_left not in self.NUMERIC_TYPES or t_right not in self.NUMERIC_TYPES:
                self.error(
                    node,
                    f"Binary operator '{op}' requires numeric operands, got '{t_left}' and '{t_right}'",
                )
                return "error"
            # Strict type checking or numeric promotion:
            if t_left != t_right:
                self.error(
                    node,
                    f"Type mismatch in binary operator '{op}': operands must have matching types, "
                    f"got '{t_left}' and '{t_right}'",
                )
                return "error"
            return t_left

        # 3. Relational operators (<, <=, >, >=)
        if op in ("<", "<=", ">", ">="):
            if t_left not in self.NUMERIC_TYPES or t_right not in self.NUMERIC_TYPES:
                self.error(
                    node,
                    f"Relational operator '{op}' requires numeric operands, got '{t_left}' and '{t_right}'",
                )
                return "error"
            if t_left != t_right:
                self.error(
                    node,
                    f"Type mismatch in relational operator '{op}': operands must have matching types, "
                    f"got '{t_left}' and '{t_right}'",
                )
                return "error"
            return "bool"

        # 4. Equality operators (==, !=)
        if op in ("==", "!="):
            if t_left != t_right:
                self.error(
                    node,
                    f"Type mismatch in equality operator '{op}': cannot compare '{t_left}' with '{t_right}'",
                )
                return "error"
            return "bool"

        # 5. Logical operators (&&, ||)
        if op in ("&&", "||"):
            if t_left != "bool" or t_right != "bool":
                self.error(
                    node,
                    f"Logical operator '{op}' requires 'bool' operands, got '{t_left}' and '{t_right}'",
                )
                return "error"
            return "bool"

        self.error(node, f"Unknown binary operator '{op}'")
        return "error"

    def visit_UnaryOp(self, node: UnaryOp) -> str:
        operand_type = self.visit(node.operand)
        if operand_type == "error":
            return "error"

        op = node.operator
        if op == "!":
            if operand_type != "bool":
                self.error(node, f"Logical NOT operator '!' requires 'bool' operand, got '{operand_type}'")
                return "error"
            return "bool"

        if op in ("-", "+"):
            if operand_type not in self.NUMERIC_TYPES:
                self.error(node, f"Unary operator '{op}' requires numeric operand, got '{operand_type}'")
                return "error"
            return operand_type

        self.error(node, f"Unknown unary operator '{op}'")
        return "error"

    def visit_Call(self, node: Call) -> str:
        sym = self.current_scope.lookup(node.callee)
        if sym is None:
            self.error(node, f"Undeclared function '{node.callee}'")
            return "error"

        if not isinstance(sym, FuncSymbol):
            self.error(node, f"'{node.callee}' is a variable, not a function")
            return "error"

        expected_count = len(sym.params)
        actual_count = len(node.args)

        if actual_count != expected_count:
            self.error(
                node,
                f"Function '{node.callee}' expects {expected_count} argument(s), got {actual_count}",
            )

        # Check types for all passed arguments up to available params
        for i, arg in enumerate(node.args):
            arg_type = self.visit(arg)
            if i < expected_count:
                expected_type, _ = sym.params[i]
                if arg_type != "error" and arg_type != expected_type:
                    self.error(
                        arg,
                        f"Argument {i + 1} of function '{node.callee}' expects type '{expected_type}', "
                        f"got '{arg_type}'",
                    )

        return sym.return_type


# ── Top-Level Analysis API ────────────────────────────────────────────────────

def analyze(ast_or_source: Union[ASTNode, str]) -> List[Diagnostic]:
    """
    Run semantic analysis on a MiniC AST or source code string.
    Returns a list of Diagnostic objects with line and column numbers.
    """
    if isinstance(ast_or_source, str):
        lexer = Lexer(ast_or_source)
        tokens = lexer.tokenize()
        if lexer.errors:
            return [
                Diagnostic(
                    message=f"Lexical error: {e.message}",
                    line=e.line,
                    column=e.column,
                    severity="error",
                )
                for e in lexer.errors
            ]
        parser = Parser(tokens)
        ast = parser.parse()
        if parser.errors:
            return [
                Diagnostic(
                    message=f"Syntax error: {e.message}",
                    line=e.line,
                    column=e.column,
                    severity="error",
                )
                for e in parser.errors
            ]
    else:
        ast = ast_or_source

    if not isinstance(ast, Program):
        raise TypeError(f"Expected Program AST node, got {type(ast).__name__}")

    analyzer = SemanticAnalyzer()
    return analyzer.analyze(ast)
