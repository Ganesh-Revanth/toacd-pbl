import os
import sys
import unittest

# Ensure src/ is on sys.path
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from core.ast_nodes import (
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
    pretty_print_ast,
)
from core.parser import Parser, ParseError


class TestMiniCParser(unittest.TestCase):
    """Comprehensive test suite for MiniC Recursive-Descent Parser."""

    # ── 1. Basic Declarations & Programs ──────────────────────────────────────

    def test_empty_program(self):
        parser = Parser("")
        prog = parser.parse()
        self.assertIsInstance(prog, Program)
        self.assertEqual(len(prog.declarations), 0)
        self.assertEqual(len(parser.errors), 0)

    def test_variable_declarations_and_assignments(self):
        source = """
        int x = 10;
        float y;
        bool flag = true;
        x = 25;
        """
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        self.assertEqual(len(prog.declarations), 4)

        # int x = 10;
        self.assertIsInstance(prog.declarations[0], VarDecl)
        self.assertEqual(prog.declarations[0].var_type, "int")
        self.assertEqual(prog.declarations[0].name, "x")
        self.assertIsInstance(prog.declarations[0].initializer, Literal)
        self.assertEqual(prog.declarations[0].initializer.value, 10)

        # float y;
        self.assertIsInstance(prog.declarations[1], VarDecl)
        self.assertEqual(prog.declarations[1].var_type, "float")
        self.assertEqual(prog.declarations[1].name, "y")
        self.assertIsNone(prog.declarations[1].initializer)

        # bool flag = true;
        self.assertIsInstance(prog.declarations[2], VarDecl)
        self.assertEqual(prog.declarations[2].var_type, "bool")
        self.assertEqual(prog.declarations[2].name, "flag")
        self.assertEqual(prog.declarations[2].initializer.value, True)

        # x = 25;
        self.assertIsInstance(prog.declarations[3], Assign)
        self.assertEqual(prog.declarations[3].target, "x")
        self.assertEqual(prog.declarations[3].value.value, 25)

    def test_function_definition_with_zero_parameters(self):
        source = "int getZero() { return 0; }"
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        self.assertEqual(len(prog.declarations), 1)
        func = prog.declarations[0]
        self.assertIsInstance(func, FunctionDef)
        self.assertEqual(func.return_type, "int")
        self.assertEqual(func.name, "getZero")
        self.assertEqual(func.params, [])
        self.assertEqual(len(func.body.statements), 1)
        self.assertIsInstance(func.body.statements[0], Return)

    def test_void_function_definition(self):
        source = 'void logMessage() { print("hello"); }'
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        func = prog.declarations[0]
        self.assertIsInstance(func, FunctionDef)
        self.assertEqual(func.return_type, "void")
        self.assertEqual(func.name, "logMessage")
        self.assertIsInstance(func.body.statements[0], Print)

    def test_function_with_multiple_parameters(self):
        source = "float compute(int a, float b, bool active) { return a + b; }"
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        func = prog.declarations[0]
        self.assertEqual(func.params, [("int", "a"), ("float", "b"), ("bool", "active")])

    def test_nested_calls(self):
        source = "int res = f(g(1), 2);"
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        decl = prog.declarations[0]
        self.assertIsInstance(decl, VarDecl)
        call_f = decl.initializer
        self.assertIsInstance(call_f, Call)
        self.assertEqual(call_f.callee, "f")
        self.assertEqual(len(call_f.args), 2)

        # arg0: g(1)
        self.assertIsInstance(call_f.args[0], Call)
        self.assertEqual(call_f.args[0].callee, "g")
        self.assertEqual(call_f.args[0].args[0].value, 1)

        # arg1: 2
        self.assertIsInstance(call_f.args[1], Literal)
        self.assertEqual(call_f.args[1].value, 2)

    def test_control_flow_and_blocks(self):
        source = """
        while (count > 0) {
            count = count - 1;
        }
        if (count == 0) {
            print count;
        } else {
            print -1;
        }
        {}
        """
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        self.assertEqual(len(prog.declarations), 3)

        # While
        self.assertIsInstance(prog.declarations[0], While)
        # If / Else
        self.assertIsInstance(prog.declarations[1], If)
        self.assertIsNotNone(prog.declarations[1].else_branch)
        # Empty block {}
        self.assertIsInstance(prog.declarations[2], Block)
        self.assertEqual(len(prog.declarations[2].statements), 0)

    def test_else_if_chains(self):
        source = """
        if (x == 1) {
            print 1;
        } else if (x == 2) {
            print 2;
        } else {
            print 3;
        }
        """
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        if_root = prog.declarations[0]
        self.assertIsInstance(if_root, If)
        self.assertIsInstance(if_root.else_branch, If)
        self.assertIsInstance(if_root.else_branch.else_branch, Block)

    def test_print_both_styles(self):
        source = "print 42; print(100);"
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        self.assertEqual(len(prog.declarations), 2)
        self.assertIsInstance(prog.declarations[0], Print)
        self.assertEqual(prog.declarations[0].expression.value, 42)
        self.assertIsInstance(prog.declarations[1], Print)
        self.assertEqual(prog.declarations[1].expression.value, 100)

    # ── 2. Tree Structure & Operator Precedence Assertions ────────────────────

    def test_multiplication_precedence_over_addition(self):
        # 1 + 2 * 3 must parse as 1 + (2 * 3)
        source = "int res = 1 + 2 * 3;"
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        decl = prog.declarations[0]
        expr = decl.initializer

        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "+")
        self.assertIsInstance(expr.left, Literal)
        self.assertEqual(expr.left.value, 1)

        self.assertIsInstance(expr.right, BinaryOp)
        self.assertEqual(expr.right.operator, "*")
        self.assertEqual(expr.right.left.value, 2)
        self.assertEqual(expr.right.right.value, 3)

    def test_parentheses_overriding_precedence(self):
        # (1 + 2) * 3 must parse as (1 + 2) * 3
        source = "int res = (1 + 2) * 3;"
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        decl = prog.declarations[0]
        expr = decl.initializer

        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "*")
        self.assertIsInstance(expr.left, BinaryOp)
        self.assertEqual(expr.left.operator, "+")
        self.assertEqual(expr.left.left.value, 1)
        self.assertEqual(expr.left.right.value, 2)
        self.assertIsInstance(expr.right, Literal)
        self.assertEqual(expr.right.value, 3)

    def test_left_associativity_subtraction(self):
        # 10 - 3 - 2 must parse as (10 - 3) - 2
        source = "int res = 10 - 3 - 2;"
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        expr = prog.declarations[0].initializer

        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.operator, "-")
        self.assertIsInstance(expr.left, BinaryOp)
        self.assertEqual(expr.left.operator, "-")
        self.assertEqual(expr.left.left.value, 10)
        self.assertEqual(expr.left.right.value, 3)
        self.assertIsInstance(expr.right, Literal)
        self.assertEqual(expr.right.value, 2)

    def test_left_associativity_division_and_modulo(self):
        # 12 / 3 / 2 must parse as (12 / 3) / 2
        source = "int d = 12 / 3 / 2; int m = 10 % 5 % 2;"
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)

        # 12 / 3 / 2
        d_expr = prog.declarations[0].initializer
        self.assertEqual(d_expr.operator, "/")
        self.assertEqual(d_expr.left.operator, "/")
        self.assertEqual(d_expr.left.left.value, 12)
        self.assertEqual(d_expr.left.right.value, 3)
        self.assertEqual(d_expr.right.value, 2)

        # 10 % 5 % 2
        m_expr = prog.declarations[1].initializer
        self.assertEqual(m_expr.operator, "%")
        self.assertEqual(m_expr.left.operator, "%")
        self.assertEqual(m_expr.left.left.value, 10)
        self.assertEqual(m_expr.left.right.value, 5)
        self.assertEqual(m_expr.right.value, 2)

    def test_unary_chains(self):
        # !!x, -(-x), a - -b
        source = """
        bool b1 = !!x;
        int n1 = -(-x);
        int n2 = a - -b;
        """
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)

        # !!x
        b1 = prog.declarations[0].initializer
        self.assertIsInstance(b1, UnaryOp)
        self.assertEqual(b1.operator, "!")
        self.assertIsInstance(b1.operand, UnaryOp)
        self.assertEqual(b1.operand.operator, "!")
        self.assertIsInstance(b1.operand.operand, Identifier)

        # -(-x)
        n1 = prog.declarations[1].initializer
        self.assertIsInstance(n1, UnaryOp)
        self.assertEqual(n1.operator, "-")
        self.assertIsInstance(n1.operand, UnaryOp)
        self.assertEqual(n1.operand.operator, "-")

        # a - -b
        n2 = prog.declarations[2].initializer
        self.assertIsInstance(n2, BinaryOp)
        self.assertEqual(n2.operator, "-")
        self.assertIsInstance(n2.left, Identifier)
        self.assertIsInstance(n2.right, UnaryOp)
        self.assertEqual(n2.right.operator, "-")

    def test_logical_operator_precedence(self):
        # a || b && c must parse as a || (b && c)
        source = "bool res = a || b && c;"
        parser = Parser(source)
        prog = parser.parse()

        self.assertEqual(len(parser.errors), 0)
        expr = prog.declarations[0].initializer
        self.assertEqual(expr.operator, "||")
        self.assertIsInstance(expr.left, Identifier)
        self.assertIsInstance(expr.right, BinaryOp)
        self.assertEqual(expr.right.operator, "&&")

    # ── 3. Five Distinct Syntax Error Tests ────────────────────────────────────

    def test_syntax_error_1_missing_semicolon_in_var_decl(self):
        source = "int x = 10"
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 1)
        err = parser.errors[0]
        self.assertEqual(err.line, 1)
        self.assertIn(";", err.expected)

    def test_syntax_error_2_missing_closing_paren_in_if(self):
        source = "if (x > 0 { print 1; }"
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 1)
        err = parser.errors[0]
        self.assertEqual(err.expected, ")")

    def test_syntax_error_3_missing_parameter_name_in_function(self):
        source = "int add(int, float b) { return 0; }"
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 1)
        err = parser.errors[0]
        self.assertIn("identifier", err.expected)

    def test_syntax_error_4_missing_closing_brace_in_function(self):
        source = "int foo() { return 1;"
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 1)
        err = parser.errors[0]
        self.assertIn("}", err.expected)

    def test_syntax_error_5_invalid_expression_token_in_assign(self):
        source = "x = * 5;"
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 1)
        err = parser.errors[0]
        self.assertIn("expression", err.expected)

    # ── 4. Multi-Error Recovery & Partial AST ──────────────────────────────────

    def test_multi_error_recovery(self):
        # Two broken statements followed by a valid one
        source = """
        int a = ;
        float b = ;
        int c = 100;
        """
        parser = Parser(source)
        prog = parser.parse()

        # Both syntax errors captured
        self.assertGreaterEqual(len(parser.errors), 2)
        # Recovered and still parsed 'int c = 100;'
        valid_decls = [d for d in prog.declarations if isinstance(d, VarDecl) and d.name == "c"]
        self.assertEqual(len(valid_decls), 1)
        self.assertEqual(valid_decls[0].initializer.value, 100)

    # ── 5. Infinite Loop Safety & Garbage Input Recovery ──────────────────────

    def test_garbage_input_closing_braces(self):
        source = "}}}}"
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 1)
        self.assertIsInstance(prog, Program)

    def test_garbage_input_lone_type(self):
        source = "int"
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 1)
        self.assertIsInstance(prog, Program)

    def test_garbage_input_incomplete_var_decl(self):
        source = "int x ="
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 1)
        self.assertIsInstance(prog, Program)

    def test_file_ends_in_middle_of_function(self):
        source = "int foo() { int x = 1; if (x > 0) {"
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 1)
        self.assertIsInstance(prog, Program)

    def test_lexer_error_tokens_handled_gracefully(self):
        # Lexical error '@' and '$' should not crash the parser
        source = "int a = @; int b = $; int c = 5;"
        parser = Parser(source)
        prog = parser.parse()

        self.assertGreaterEqual(len(parser.errors), 2)
        valid_c = [d for d in prog.declarations if isinstance(d, VarDecl) and d.name == "c"]
        self.assertEqual(len(valid_c), 1)

    # ── 6. AST Pretty-Printer ─────────────────────────────────────────────────

    def test_pretty_printer(self):
        source = "int add(int a, int b) { return a + b; }"
        parser = Parser(source)
        prog = parser.parse()

        formatted = pretty_print_ast(prog)
        self.assertIn("Program", formatted)
        self.assertIn("FunctionDef: int add(int a, int b)", formatted)
        self.assertIn("BinaryOp ('+')", formatted)
        self.assertIn("Return", formatted)


if __name__ == "__main__":
    unittest.main()
