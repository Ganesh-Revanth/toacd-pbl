"""
lexer.py
--------
Lexical analyzer (scanner) for the MiniC programming language.

Features:
  - Token dataclass with type, lexeme, line, column, and optional parsed literal value.
  - Full keyword set: int, float, bool, if, else, while, return, print, true, false, void.
  - Multi-character relational and logical operators: ==, !=, <=, >=, &&, ||.
  - Single-character operators: +, -, *, /, %, <, >, !, =.
  - Delimiters: (, ), {, }, ;, ,.
  - Integer, float, and escaped string literals.
  - Line comments starting with '//'.
  - Resilient error handling: unknown characters and unterminated strings are
    recorded in `lexer.errors` with line & column and emitted as ERROR tokens
    instead of raising unhandled exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional


class TokenType(Enum):
    # Keywords
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    RETURN = "return"
    PRINT = "print"
    TRUE = "true"
    FALSE = "false"
    VOID = "void"

    # Literals & Identifiers
    IDENTIFIER = "IDENTIFIER"
    INT_LITERAL = "INT_LITERAL"
    FLOAT_LITERAL = "FLOAT_LITERAL"
    STRING_LITERAL = "STRING_LITERAL"

    # Arithmetic & Assignment Operators
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    ASSIGN = "="

    # Relational Operators
    EQUAL_EQUAL = "=="
    BANG_EQUAL = "!="
    LESS = "<"
    GREATER = ">"
    LESS_EQUAL = "<="
    GREATER_EQUAL = ">="

    # Logical Operators
    AMP_AMP = "&&"
    PIPE_PIPE = "||"
    BANG = "!"

    # Delimiters
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    SEMICOLON = ";"
    COMMA = ","

    # Special
    EOF = "EOF"
    ERROR = "ERROR"

    def __str__(self) -> str:
        return self.value


KEYWORDS: Dict[str, TokenType] = {
    "int": TokenType.INT,
    "float": TokenType.FLOAT,
    "bool": TokenType.BOOL,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "return": TokenType.RETURN,
    "print": TokenType.PRINT,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "void": TokenType.VOID,
}


@dataclass
class Token:
    type: TokenType
    lexeme: str
    line: int
    column: int
    literal: Optional[Any] = None

    def __repr__(self) -> str:
        lit_str = f", literal={self.literal!r}" if self.literal is not None else ""
        return f"Token({self.type.name}, {self.lexeme!r}, line={self.line}, col={self.column}{lit_str})"


@dataclass
class LexerError:
    message: str
    line: int
    column: int
    char: str


class Lexer:
    """
    MiniC Lexer. Converts raw MiniC source text into a stream of Token objects.
    """

    def __init__(self, source: str) -> None:
        self.source: str = source
        self.length: int = len(source)
        self.start: int = 0
        self.current: int = 0
        self.line: int = 1
        self.column: int = 1
        self.start_column: int = 1
        self.errors: List[LexerError] = []

    def is_at_end(self) -> bool:
        return self.current >= self.length

    def advance(self) -> str:
        char = self.source[self.current]
        self.current += 1
        self.column += 1
        return char

    def peek(self) -> str:
        if self.is_at_end():
            return "\0"
        return self.source[self.current]

    def peek_next(self) -> str:
        if self.current + 1 >= self.length:
            return "\0"
        return self.source[self.current + 1]

    def match(self, expected: str) -> bool:
        if self.is_at_end() or self.source[self.current] != expected:
            return False
        self.current += 1
        self.column += 1
        return True

    def _make_token(self, token_type: TokenType, literal: Optional[Any] = None) -> Token:
        lexeme = self.source[self.start : self.current]
        return Token(
            type=token_type,
            lexeme=lexeme,
            line=self.line,
            column=self.start_column,
            literal=literal,
        )

    def _report_error(self, message: str, char: str) -> Token:
        err = LexerError(message=message, line=self.line, column=self.start_column, char=char)
        self.errors.append(err)
        return Token(
            type=TokenType.ERROR,
            lexeme=char,
            line=self.line,
            column=self.start_column,
            literal=message,
        )

    def _skip_whitespace_and_comments(self) -> None:
        while not self.is_at_end():
            c = self.peek()
            if c in (" ", "\t", "\r"):
                self.advance()
            elif c == "\n":
                self.advance()
                self.line += 1
                self.column = 1
            elif c == "/" and self.peek_next() == "/":
                # Single line comment: consume until newline or EOF
                self.advance()
                self.advance()
                while not self.is_at_end() and self.peek() != "\n":
                    self.advance()
            else:
                break

    def _string(self) -> Token:
        chars: List[str] = []
        start_line = self.line
        start_col = self.start_column

        while not self.is_at_end() and self.peek() != '"':
            c = self.advance()
            if c == "\n":
                self.line += 1
                self.column = 1
                # MiniC does not allow raw multiline unescaped newlines in strings
                err = LexerError(
                    message="Unterminated string literal (newline encountered)",
                    line=start_line,
                    column=start_col,
                    char="\n",
                )
                self.errors.append(err)
                return Token(
                    type=TokenType.ERROR,
                    lexeme=self.source[self.start : self.current - 1],
                    line=start_line,
                    column=start_col,
                    literal=err.message,
                )
            if c == "\\":
                if self.is_at_end():
                    break
                escape = self.advance()
                escape_map = {
                    "n": "\n",
                    "t": "\t",
                    "r": "\r",
                    '"': '"',
                    "\\": "\\",
                    "0": "\0",
                }
                chars.append(escape_map.get(escape, escape))
            else:
                chars.append(c)

        if self.is_at_end():
            err = LexerError(
                message="Unterminated string literal at end of file",
                line=start_line,
                column=start_col,
                char='"'
            )
            self.errors.append(err)
            return Token(
                type=TokenType.ERROR,
                lexeme=self.source[self.start : self.current],
                line=start_line,
                column=start_col,
                literal=err.message,
            )

        # Consume closing quote
        self.advance()
        parsed_value = "".join(chars)
        return self._make_token(TokenType.STRING_LITERAL, literal=parsed_value)

    def _number(self) -> Token:
        while self.peek().isdigit():
            self.advance()

        # Check for fractional part
        if self.peek() == "." and self.peek_next().isdigit():
            # Consume '.'
            self.advance()
            while self.peek().isdigit():
                self.advance()
            val_str = self.source[self.start : self.current]
            return self._make_token(TokenType.FLOAT_LITERAL, literal=float(val_str))

        val_str = self.source[self.start : self.current]
        return self._make_token(TokenType.INT_LITERAL, literal=int(val_str))

    def _identifier_or_keyword(self) -> Token:
        while self.peek().isalnum() or self.peek() == "_":
            self.advance()

        text = self.source[self.start : self.current]
        token_type = KEYWORDS.get(text, TokenType.IDENTIFIER)
        literal = None
        if token_type == TokenType.TRUE:
            literal = True
        elif token_type == TokenType.FALSE:
            literal = False

        return self._make_token(token_type, literal=literal)

    def next_token(self) -> Token:
        """Scan and return the next single token."""
        self._skip_whitespace_and_comments()

        self.start = self.current
        self.start_column = self.column

        if self.is_at_end():
            return Token(TokenType.EOF, "", self.line, self.column)

        c = self.advance()

        # Identifiers and keywords
        if c.isalpha() or c == "_":
            return self._identifier_or_keyword()

        # Digits (integers and floats)
        if c.isdigit():
            return self._number()

        # String literals
        if c == '"':
            return self._string()

        # Operators and punctuation
        if c == "(":
            return self._make_token(TokenType.LPAREN)
        if c == ")":
            return self._make_token(TokenType.RPAREN)
        if c == "{":
            return self._make_token(TokenType.LBRACE)
        if c == "}":
            return self._make_token(TokenType.RBRACE)
        if c == ";":
            return self._make_token(TokenType.SEMICOLON)
        if c == ",":
            return self._make_token(TokenType.COMMA)
        if c == "+":
            return self._make_token(TokenType.PLUS)
        if c == "-":
            return self._make_token(TokenType.MINUS)
        if c == "*":
            return self._make_token(TokenType.STAR)
        if c == "/":
            return self._make_token(TokenType.SLASH)
        if c == "%":
            return self._make_token(TokenType.PERCENT)

        if c == "=":
            return self._make_token(TokenType.EQUAL_EQUAL if self.match("=") else TokenType.ASSIGN)
        if c == "!":
            return self._make_token(TokenType.BANG_EQUAL if self.match("=") else TokenType.BANG)
        if c == "<":
            return self._make_token(TokenType.LESS_EQUAL if self.match("=") else TokenType.LESS)
        if c == ">":
            return self._make_token(TokenType.GREATER_EQUAL if self.match("=") else TokenType.GREATER)

        if c == "&":
            if self.match("&"):
                return self._make_token(TokenType.AMP_AMP)
            return self._report_error("Unexpected '&', expected '&&'", "&")

        if c == "|":
            if self.match("|"):
                return self._make_token(TokenType.PIPE_PIPE)
            return self._report_error("Unexpected '|', expected '||'", "|")

        # Unknown / invalid character
        return self._report_error(f"Unknown character '{c}'", c)

    def tokenize(self) -> List[Token]:
        """Collect and return all tokens up to and including EOF."""
        tokens: List[Token] = []
        while True:
            tok = self.next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF:
                break
        return tokens

    def __iter__(self) -> Iterator[Token]:
        """Stream tokens sequentially."""
        while True:
            tok = self.next_token()
            yield tok
            if tok.type == TokenType.EOF:
                break
