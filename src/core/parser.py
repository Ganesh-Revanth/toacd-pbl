"""
parser.py
---------
Recursive-descent parser for MiniC producing an Abstract Syntax Tree (AST).

MiniC Grammar in Backus-Naur Form (BNF):
========================================
Program        ::= ( FunctionDef | VarDecl | Statement )* EOF

FunctionDef    ::= Type IDENTIFIER "(" Parameters? ")" Block
Parameters     ::= Parameter ( "," Parameter )*
Parameter      ::= Type IDENTIFIER
Type           ::= "int" | "float" | "bool" | "void"

Block          ::= "{" Statement* "}"

Statement      ::= VarDecl
                 | AssignStmt
                 | IfStmt
                 | WhileStmt
                 | ReturnStmt
                 | PrintStmt
                 | Block
                 | ExprStmt
                 | ";"

VarDecl        ::= Type IDENTIFIER ( "=" Expression )? ";"
AssignStmt     ::= IDENTIFIER "=" Expression ";"
IfStmt         ::= "if" "(" Expression ")" Statement ( "else" Statement )?
WhileStmt      ::= "while" "(" Expression ")" Statement
ReturnStmt     ::= "return" Expression? ";"

PrintStmt      ::= "print" ( "(" Expression ")" | Expression ) ";"
                   -- Supports both 'print(expr);' (function-style) and
                   -- 'print expr;' (keyword statement style).

ExprStmt       ::= Expression ";"

Expression     ::= LogicalOr
LogicalOr      ::= LogicalAnd ( "||" LogicalAnd )*
LogicalAnd     ::= Equality ( "&&" Equality )*
Equality       ::= Relational ( ( "==" | "!=" ) Relational )*
Relational     ::= Additive ( ( "<" | "<=" | ">" | ">=" ) Additive )*
Additive       ::= Multiplicative ( ( "+" | "-" ) Multiplicative )*
Multiplicative ::= Unary ( ( "*" | "/" | "%" ) Unary )*
Unary          ::= ( "!" | "-" | "+" ) Unary | Primary
Primary        ::= Literal
                 | IDENTIFIER ( "(" Arguments? ")" )?
                 | "(" Expression ")"

Arguments      ::= Expression ( "," Expression )*
Literal        ::= INT_LITERAL | FLOAT_LITERAL | STRING_LITERAL | "true" | "false"

Operator Precedence (lowest to highest):
----------------------------------------
1. Logical OR:       ||
2. Logical AND:      &&
3. Equality:         ==, !=
4. Relational:       <, <=, >, >=
5. Additive:         +, -
6. Multiplicative:   *, /, %
7. Unary:            !, -, +
8. Primary / Calls:  (), Literals, Identifiers
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

from .ast_nodes import (
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
from .lexer import Lexer, Token, TokenType


@dataclass
class ParseError:
    message: str
    line: int
    column: int
    expected: str = ""

    def __str__(self) -> str:
        exp = f" (expected {self.expected})" if self.expected else ""
        return f"[Line {self.line}:{self.column}] Syntax Error: {self.message}{exp}"


class Parser:
    """
    MiniC Recursive-Descent Parser.
    Recovers from syntax errors at ';' and '}' boundaries to collect multiple errors.
    """

    TYPE_TOKENS = (TokenType.INT, TokenType.FLOAT, TokenType.BOOL, TokenType.VOID)

    def __init__(self, tokens_or_source: Union[List[Token], str]) -> None:
        if isinstance(tokens_or_source, str):
            lexer = Lexer(tokens_or_source)
            self.tokens = lexer.tokenize()
            # Capture lexer-level errors immediately
            self.errors: List[ParseError] = [
                ParseError(
                    message=e.message,
                    line=e.line,
                    column=e.column,
                    expected="valid token",
                )
                for e in lexer.errors
            ]
        else:
            self.tokens = tokens_or_source
            self.errors = []

        self.current = 0

    # ── Token Navigation Helpers ──────────────────────────────────────────────

    def is_at_end(self) -> bool:
        return self.peek().type == TokenType.EOF

    def peek(self) -> Token:
        return self.tokens[self.current]

    def previous(self) -> Token:
        return self.tokens[self.current - 1]

    def check(self, token_type: TokenType) -> bool:
        if self.is_at_end():
            return token_type == TokenType.EOF
        return self.peek().type == token_type

    def advance(self) -> Token:
        if not self.is_at_end():
            self.current += 1
        return self.previous()

    def match(self, *types: TokenType) -> bool:
        for t in types:
            if self.check(t):
                self.advance()
                return True
        return False

    def peek_next(self) -> Token:
        if self.current + 1 < len(self.tokens):
            return self.tokens[self.current + 1]
        return self.tokens[-1]

    def peek_after_next(self) -> Token:
        if self.current + 2 < len(self.tokens):
            return self.tokens[self.current + 2]
        return self.tokens[-1]

    # ── Error Reporting & Panic-Mode Recovery ─────────────────────────────────

    def error(self, token: Token, message: str, expected: str = "") -> None:
        # Avoid duplicate error reports on lexer ERROR tokens
        if token.type == TokenType.ERROR:
            err = ParseError(
                message=f"Lexical error: {token.literal or token.lexeme}",
                line=token.line,
                column=token.column,
                expected=expected,
            )
        else:
            err = ParseError(
                message=message,
                line=token.line,
                column=token.column,
                expected=expected,
            )
        self.errors.append(err)

    def consume(self, token_type: TokenType, message: str, expected: str = "") -> Token:
        if self.check(token_type):
            return self.advance()
        tok = self.peek()
        self.error(tok, message, expected=expected or token_type.value)
        raise SyntaxError(message)

    def synchronize(self) -> None:
        """
        Panic-mode error recovery.
        Always consumes at least one token to prevent infinite loops.
        Recovers at ';' or '}' or beginning of next statement.
        """
        if self.is_at_end():
            return

        # Always consume at least one token
        self.advance()

        while not self.is_at_end():
            if self.previous().type in (TokenType.SEMICOLON, TokenType.RBRACE):
                return

            if self.peek().type in (
                TokenType.INT,
                TokenType.FLOAT,
                TokenType.BOOL,
                TokenType.VOID,
                TokenType.IF,
                TokenType.WHILE,
                TokenType.RETURN,
                TokenType.PRINT,
                TokenType.RBRACE,
            ):
                return

            self.advance()

    # ── Parsing Methods ───────────────────────────────────────────────────────

    def parse(self) -> Program:
        """Parse all declarations and statements into a Program AST."""
        program = Program(declarations=[], line=1, column=1)

        while not self.is_at_end():
            # Handle standalone lexer errors gracefully
            if self.check(TokenType.ERROR):
                err_tok = self.advance()
                self.error(err_tok, f"Unexpected token: '{err_tok.lexeme}'", expected="valid declaration")
                continue

            try:
                decl = self.declaration()
                if decl is not None:
                    program.declarations.append(decl)
            except SyntaxError:
                self.synchronize()

        return program

    def declaration(self) -> Optional[ASTNode]:
        """Parse function definition, variable declaration, or general statement."""
        if self.check_any(*self.TYPE_TOKENS):
            if self.peek_next().type == TokenType.IDENTIFIER and self.peek_after_next().type == TokenType.LPAREN:
                return self.function_def()
            return self.var_decl()

        return self.statement()

    def check_any(self, *types: TokenType) -> bool:
        return any(self.check(t) for t in types)

    def function_def(self) -> FunctionDef:
        type_tok = self.advance()
        return_type = type_tok.lexeme
        name_tok = self.consume(TokenType.IDENTIFIER, "expected function name", expected="identifier")
        func_name = name_tok.lexeme

        self.consume(TokenType.LPAREN, "expected '(' after function name", expected="(")
        params: List[Tuple[str, str]] = []

        if not self.check(TokenType.RPAREN):
            while True:
                if not self.check_any(*self.TYPE_TOKENS):
                    tok = self.peek()
                    self.error(tok, f"expected parameter type, found '{tok.lexeme}'", expected="type (int, float, bool, void)")
                    raise SyntaxError("parameter type missing")

                p_type_tok = self.advance()
                p_name_tok = self.consume(TokenType.IDENTIFIER, "expected parameter name", expected="identifier")
                params.append((p_type_tok.lexeme, p_name_tok.lexeme))

                if not self.match(TokenType.COMMA):
                    break

        self.consume(TokenType.RPAREN, "expected ')' after parameters", expected=")")
        body = self.block()

        return FunctionDef(
            return_type=return_type,
            name=func_name,
            params=params,
            body=body,
            line=type_tok.line,
            column=type_tok.column,
        )

    def var_decl(self) -> VarDecl:
        type_tok = self.advance()
        name_tok = self.consume(TokenType.IDENTIFIER, "expected variable name", expected="identifier")
        initializer: Optional[ASTNode] = None

        if self.match(TokenType.ASSIGN):
            initializer = self.expression()

        self.consume(TokenType.SEMICOLON, "expected ';' after variable declaration", expected=";")
        return VarDecl(
            var_type=type_tok.lexeme,
            name=name_tok.lexeme,
            initializer=initializer,
            line=type_tok.line,
            column=type_tok.column,
        )

    def statement(self) -> ASTNode:
        """Parse a single statement."""
        if self.check_any(*self.TYPE_TOKENS):
            return self.var_decl()
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.PRINT):
            return self.print_statement()
        if self.check(TokenType.LBRACE):
            return self.block()
        if self.match(TokenType.SEMICOLON):
            # Empty statement
            return Block(statements=[], line=self.previous().line, column=self.previous().column)

        # Assignment or Expression Statement
        if self.check(TokenType.IDENTIFIER) and self.peek_next().type == TokenType.ASSIGN:
            return self.assign_statement()

        return self.expr_statement()

    def block(self) -> Block:
        lbrace = self.consume(TokenType.LBRACE, "expected '{' at start of block", expected="{")
        statements: List[ASTNode] = []

        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            try:
                stmt = self.statement()
                if stmt is not None:
                    statements.append(stmt)
            except SyntaxError:
                self.synchronize()

        self.consume(TokenType.RBRACE, "expected '}' at end of block", expected="}")
        return Block(statements=statements, line=lbrace.line, column=lbrace.column)

    def if_statement(self) -> If:
        if_tok = self.previous()
        self.consume(TokenType.LPAREN, "expected '(' after 'if'", expected="(")
        condition = self.expression()
        self.consume(TokenType.RPAREN, "expected ')' after if condition", expected=")")

        then_branch = self.statement()
        else_branch: Optional[ASTNode] = None
        if self.match(TokenType.ELSE):
            else_branch = self.statement()

        return If(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            line=if_tok.line,
            column=if_tok.column,
        )

    def while_statement(self) -> While:
        while_tok = self.previous()
        self.consume(TokenType.LPAREN, "expected '(' after 'while'", expected="(")
        condition = self.expression()
        self.consume(TokenType.RPAREN, "expected ')' after while condition", expected=")")
        body = self.statement()

        return While(
            condition=condition,
            body=body,
            line=while_tok.line,
            column=while_tok.column,
        )

    def return_statement(self) -> Return:
        ret_tok = self.previous()
        val: Optional[ASTNode] = None
        if not self.check(TokenType.SEMICOLON):
            val = self.expression()

        self.consume(TokenType.SEMICOLON, "expected ';' after return statement", expected=";")
        return Return(value=val, line=ret_tok.line, column=ret_tok.column)

    def print_statement(self) -> Print:
        print_tok = self.previous()
        has_paren = False

        # Support both 'print(expr);' and 'print expr;'
        if self.match(TokenType.LPAREN):
            has_paren = True

        expr = self.expression()

        if has_paren:
            self.consume(TokenType.RPAREN, "expected ')' after print expression", expected=")")

        self.consume(TokenType.SEMICOLON, "expected ';' after print statement", expected=";")
        return Print(expression=expr, line=print_tok.line, column=print_tok.column)

    def assign_statement(self) -> Assign:
        id_tok = self.advance()
        self.consume(TokenType.ASSIGN, "expected '=' in assignment", expected="=")
        val = self.expression()
        self.consume(TokenType.SEMICOLON, "expected ';' after assignment", expected=";")
        return Assign(
            target=id_tok.lexeme,
            value=val,
            line=id_tok.line,
            column=id_tok.column,
        )

    def expr_statement(self) -> ExprStmt:
        expr = self.expression()
        self.consume(TokenType.SEMICOLON, "expected ';' after expression statement", expected=";")
        return ExprStmt(expr=expr, line=expr.line, column=expr.column)

    # ── Expressions with Operator Precedence ──────────────────────────────────

    def expression(self) -> ASTNode:
        return self.logical_or()

    def logical_or(self) -> ASTNode:
        expr = self.logical_and()
        while self.match(TokenType.PIPE_PIPE):
            op_tok = self.previous()
            right = self.logical_and()
            expr = BinaryOp(
                left=expr,
                operator=op_tok.lexeme,
                right=right,
                line=op_tok.line,
                column=op_tok.column,
            )
        return expr

    def logical_and(self) -> ASTNode:
        expr = self.equality()
        while self.match(TokenType.AMP_AMP):
            op_tok = self.previous()
            right = self.equality()
            expr = BinaryOp(
                left=expr,
                operator=op_tok.lexeme,
                right=right,
                line=op_tok.line,
                column=op_tok.column,
            )
        return expr

    def equality(self) -> ASTNode:
        expr = self.relational()
        while self.match(TokenType.EQUAL_EQUAL, TokenType.BANG_EQUAL):
            op_tok = self.previous()
            right = self.relational()
            expr = BinaryOp(
                left=expr,
                operator=op_tok.lexeme,
                right=right,
                line=op_tok.line,
                column=op_tok.column,
            )
        return expr

    def relational(self) -> ASTNode:
        expr = self.additive()
        while self.match(TokenType.LESS, TokenType.LESS_EQUAL, TokenType.GREATER, TokenType.GREATER_EQUAL):
            op_tok = self.previous()
            right = self.additive()
            expr = BinaryOp(
                left=expr,
                operator=op_tok.lexeme,
                right=right,
                line=op_tok.line,
                column=op_tok.column,
            )
        return expr

    def additive(self) -> ASTNode:
        # Left-associative addition and subtraction
        expr = self.multiplicative()
        while self.match(TokenType.PLUS, TokenType.MINUS):
            op_tok = self.previous()
            right = self.multiplicative()
            expr = BinaryOp(
                left=expr,
                operator=op_tok.lexeme,
                right=right,
                line=op_tok.line,
                column=op_tok.column,
            )
        return expr

    def multiplicative(self) -> ASTNode:
        # Left-associative multiplication, division, and modulo
        expr = self.unary()
        while self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_tok = self.previous()
            right = self.unary()
            expr = BinaryOp(
                left=expr,
                operator=op_tok.lexeme,
                right=right,
                line=op_tok.line,
                column=op_tok.column,
            )
        return expr

    def unary(self) -> ASTNode:
        # Right-associative unary prefix operators (!, -, +)
        if self.match(TokenType.BANG, TokenType.MINUS, TokenType.PLUS):
            op_tok = self.previous()
            operand = self.unary()
            return UnaryOp(
                operator=op_tok.lexeme,
                operand=operand,
                line=op_tok.line,
                column=op_tok.column,
            )
        return self.primary()

    def primary(self) -> ASTNode:
        tok = self.peek()

        if self.match(TokenType.INT_LITERAL):
            return Literal(value=tok.literal, literal_type="int", line=tok.line, column=tok.column)

        if self.match(TokenType.FLOAT_LITERAL):
            return Literal(value=tok.literal, literal_type="float", line=tok.line, column=tok.column)

        if self.match(TokenType.STRING_LITERAL):
            return Literal(value=tok.literal, literal_type="string", line=tok.line, column=tok.column)

        if self.match(TokenType.TRUE):
            return Literal(value=True, literal_type="bool", line=tok.line, column=tok.column)

        if self.match(TokenType.FALSE):
            return Literal(value=False, literal_type="bool", line=tok.line, column=tok.column)

        if self.match(TokenType.IDENTIFIER):
            id_name = tok.lexeme
            # Function Call: identifier followed by '('
            if self.match(TokenType.LPAREN):
                args: List[ASTNode] = []
                if not self.check(TokenType.RPAREN):
                    while True:
                        args.append(self.expression())
                        if not self.match(TokenType.COMMA):
                            break
                self.consume(TokenType.RPAREN, "expected ')' after arguments", expected=")")
                return Call(callee=id_name, args=args, line=tok.line, column=tok.column)

            return Identifier(name=id_name, line=tok.line, column=tok.column)

        if self.match(TokenType.LPAREN):
            expr = self.expression()
            self.consume(TokenType.RPAREN, "expected ')' after parenthesized expression", expected=")")
            return expr

        # Invalid token in expression position
        self.error(tok, f"unexpected token in expression: '{tok.lexeme}'", expected="expression")
        raise SyntaxError(f"unexpected expression token '{tok.lexeme}'")
