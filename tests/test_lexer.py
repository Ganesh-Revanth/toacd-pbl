import os
import sys
import unittest

# Ensure src/ is on sys.path
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from core.lexer import Lexer, Token, TokenType, LexerError


class TestMiniCLexer(unittest.TestCase):
    """Comprehensive test suite for MiniC Lexer."""

    def test_keywords(self):
        source = "int float bool if else while return print true false void"
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        expected_types = [
            TokenType.INT,
            TokenType.FLOAT,
            TokenType.BOOL,
            TokenType.IF,
            TokenType.ELSE,
            TokenType.WHILE,
            TokenType.RETURN,
            TokenType.PRINT,
            TokenType.TRUE,
            TokenType.FALSE,
            TokenType.VOID,
            TokenType.EOF,
        ]
        self.assertEqual([t.type for t in tokens], expected_types)
        self.assertEqual(len(lexer.errors), 0)

    def test_identifiers(self):
        source = "foo bar_123 _private countX"
        tokens = Lexer(source).tokenize()

        self.assertEqual(
            [t.type for t in tokens],
            [TokenType.IDENTIFIER, TokenType.IDENTIFIER, TokenType.IDENTIFIER, TokenType.IDENTIFIER, TokenType.EOF],
        )
        self.assertEqual([t.lexeme for t in tokens[:-1]], ["foo", "bar_123", "_private", "countX"])

    def test_integer_literals(self):
        source = "0 42 123456"
        tokens = Lexer(source).tokenize()

        self.assertEqual([t.type for t in tokens[:-1]], [TokenType.INT_LITERAL, TokenType.INT_LITERAL, TokenType.INT_LITERAL])
        self.assertEqual([t.literal for t in tokens[:-1]], [0, 42, 123456])

    def test_float_literals(self):
        source = "0.0 3.14159 42.5"
        tokens = Lexer(source).tokenize()

        self.assertEqual([t.type for t in tokens[:-1]], [TokenType.FLOAT_LITERAL, TokenType.FLOAT_LITERAL, TokenType.FLOAT_LITERAL])
        self.assertAlmostEqual(tokens[0].literal, 0.0)
        self.assertAlmostEqual(tokens[1].literal, 3.14159)
        self.assertAlmostEqual(tokens[2].literal, 42.5)

    def test_string_literals(self):
        source = r'"hello world" "escaped \"quotes\"" "tab\tand\nnewline" ""'
        tokens = Lexer(source).tokenize()

        self.assertEqual(
            [t.type for t in tokens[:-1]],
            [TokenType.STRING_LITERAL, TokenType.STRING_LITERAL, TokenType.STRING_LITERAL, TokenType.STRING_LITERAL],
        )
        self.assertEqual(tokens[0].literal, "hello world")
        self.assertEqual(tokens[1].literal, 'escaped "quotes"')
        self.assertEqual(tokens[2].literal, "tab\tand\nnewline")
        self.assertEqual(tokens[3].literal, "")

    def test_operators(self):
        source = "+ - * / % == != < > <= >= && || ! ="
        tokens = Lexer(source).tokenize()

        expected_types = [
            TokenType.PLUS,
            TokenType.MINUS,
            TokenType.STAR,
            TokenType.SLASH,
            TokenType.PERCENT,
            TokenType.EQUAL_EQUAL,
            TokenType.BANG_EQUAL,
            TokenType.LESS,
            TokenType.GREATER,
            TokenType.LESS_EQUAL,
            TokenType.GREATER_EQUAL,
            TokenType.AMP_AMP,
            TokenType.PIPE_PIPE,
            TokenType.BANG,
            TokenType.ASSIGN,
            TokenType.EOF,
        ]
        self.assertEqual([t.type for t in tokens], expected_types)

    def test_delimiters(self):
        source = "() {} ; ,"
        tokens = Lexer(source).tokenize()

        expected = [
            TokenType.LPAREN,
            TokenType.RPAREN,
            TokenType.LBRACE,
            TokenType.RBRACE,
            TokenType.SEMICOLON,
            TokenType.COMMA,
            TokenType.EOF,
        ]
        self.assertEqual([t.type for t in tokens], expected)

    def test_function_definition_with_parameters(self):
        source = """
        int add(int a, float b) {
            return a + b;
        }
        """
        tokens = Lexer(source).tokenize()

        expected_sequence = [
            (TokenType.INT, "int"),
            (TokenType.IDENTIFIER, "add"),
            (TokenType.LPAREN, "("),
            (TokenType.INT, "int"),
            (TokenType.IDENTIFIER, "a"),
            (TokenType.COMMA, ","),
            (TokenType.FLOAT, "float"),
            (TokenType.IDENTIFIER, "b"),
            (TokenType.RPAREN, ")"),
            (TokenType.LBRACE, "{"),
            (TokenType.RETURN, "return"),
            (TokenType.IDENTIFIER, "a"),
            (TokenType.PLUS, "+"),
            (TokenType.IDENTIFIER, "b"),
            (TokenType.SEMICOLON, ";"),
            (TokenType.RBRACE, "}"),
            (TokenType.EOF, ""),
        ]

        self.assertEqual([(t.type, t.lexeme) for t in tokens], expected_sequence)

    def test_single_line_comments(self):
        source = """
        // This is a leading comment
        int x = 10; // trailing comment
        // Another standalone comment
        print x;
        """
        tokens = Lexer(source).tokenize()

        expected_sequence = [
            (TokenType.INT, "int"),
            (TokenType.IDENTIFIER, "x"),
            (TokenType.ASSIGN, "="),
            (TokenType.INT_LITERAL, "10"),
            (TokenType.SEMICOLON, ";"),
            (TokenType.PRINT, "print"),
            (TokenType.IDENTIFIER, "x"),
            (TokenType.SEMICOLON, ";"),
            (TokenType.EOF, ""),
        ]
        self.assertEqual([(t.type, t.lexeme) for t in tokens], expected_sequence)

    def test_line_and_column_tracking(self):
        source = "int x;\n  float y = 3.5;"
        tokens = Lexer(source).tokenize()

        # int
        self.assertEqual((tokens[0].line, tokens[0].column), (1, 1))
        # x
        self.assertEqual((tokens[1].line, tokens[1].column), (1, 5))
        # ;
        self.assertEqual((tokens[2].line, tokens[2].column), (1, 6))
        # float (line 2, col 3)
        self.assertEqual((tokens[3].line, tokens[3].column), (2, 3))
        # y
        self.assertEqual((tokens[4].line, tokens[4].column), (2, 9))
        # =
        self.assertEqual((tokens[5].line, tokens[5].column), (2, 11))
        # 3.5
        self.assertEqual((tokens[6].line, tokens[6].column), (2, 13))

    def test_unknown_character_handling(self):
        source = "int a = @ + $;"
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        # Should not crash and should record errors with line and column
        self.assertEqual(len(lexer.errors), 2)
        err1, err2 = lexer.errors

        self.assertEqual(err1.char, "@")
        self.assertEqual(err1.line, 1)
        self.assertEqual(err1.column, 9)

        self.assertEqual(err2.char, "$")
        self.assertEqual(err2.line, 1)
        self.assertEqual(err2.column, 13)

        # ERROR tokens emitted in token stream
        error_tokens = [t for t in tokens if t.type == TokenType.ERROR]
        self.assertEqual(len(error_tokens), 2)
        self.assertEqual([t.lexeme for t in error_tokens], ["@", "$"])

        # Subsequent valid tokens are still lexed
        self.assertEqual(tokens[-2].type, TokenType.SEMICOLON)

    def test_incomplete_logical_operators(self):
        source = "a & b | c"
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        self.assertEqual(len(lexer.errors), 2)
        self.assertIn("expected '&&'", lexer.errors[0].message)
        self.assertIn("expected '||'", lexer.errors[1].message)

    def test_unterminated_string_literal(self):
        source = 'int x = "unterminated;'
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        self.assertTrue(any(t.type == TokenType.ERROR for t in tokens))
        self.assertEqual(len(lexer.errors), 1)
        self.assertIn("Unterminated string", lexer.errors[0].message)
        self.assertEqual(lexer.errors[0].line, 1)
        self.assertEqual(lexer.errors[0].column, 9)

    def test_generator_iteration(self):
        source = "while (x > 0) x = x - 1;"
        token_types = [t.type for t in Lexer(source)]
        self.assertIn(TokenType.WHILE, token_types)
        self.assertEqual(token_types[-1], TokenType.EOF)


if __name__ == "__main__":
    unittest.main()
