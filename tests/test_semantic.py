"""
test_semantic.py
----------------
Comprehensive test suite for MiniC semantic analyzer and scoped symbol table.
Tests cover:
  1. Undeclared variables and functions.
  2. Redeclaration in the same scope (and allowed shadowing in nested scopes).
  3. Type mismatches in assignments, initializations, and binary/unary operations.
  4. Wrong argument count or types in function calls.
  5. Missing returns in non-void functions and return type checking.
  6. Use before initialization.
"""

import os
import sys
import unittest

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from core.ast_nodes import Program
from core.semantic import (
    Diagnostic,
    FuncSymbol,
    SemanticAnalyzer,
    SymbolTable,
    VarSymbol,
    analyze,
)


class TestMiniCSemanticAnalyzer(unittest.TestCase):
    """Unit tests for MiniC semantic analysis and symbol resolution."""

    # ── 1. Undeclared Variables and Functions ─────────────────────────────────

    def test_undeclared_variable_in_expression(self):
        source = """
        int main() {
            int x = y + 1;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Undeclared variable 'y'", diags[0].message)
        self.assertEqual(diags[0].line, 3)

    def test_undeclared_variable_in_assignment(self):
        source = """
        int main() {
            target = 42;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Undeclared variable 'target'", diags[0].message)

    def test_undeclared_function_call(self):
        source = """
        int main() {
            unknown_func(1, 2);
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Undeclared function 'unknown_func'", diags[0].message)

    # ── 2. Redeclaration in Same Scope & Shadowing ────────────────────────────

    def test_variable_redeclaration_in_same_scope(self):
        source = """
        int main() {
            int a = 10;
            int a = 20;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Redeclaration of variable 'a' in the same scope", diags[0].message)

    def test_function_redeclaration(self):
        source = """
        void foo() {}
        void foo() {}
        int main() {
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Redeclaration of function 'foo'", diags[0].message)

    def test_parameter_redeclaration_in_signature(self):
        source = """
        int add(int x, int x) {
            return x;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Redeclaration of parameter 'x'", diags[0].message)

    def test_variable_redeclares_parameter_in_function_body(self):
        source = """
        int compute(int x) {
            int x = 5;
            return x;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Redeclaration of variable 'x' in the same scope", diags[0].message)

    def test_shadowing_in_nested_block_is_allowed(self):
        source = """
        int main() {
            int x = 10;
            {
                int x = 20;
                print(x);
            }
            return x;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 0)

    # ── 3. Type Mismatches in Assignments & Binary Operations ──────────────────

    def test_type_mismatch_in_initialization(self):
        source = """
        int main() {
            int x = 3.14;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Cannot initialize variable 'x' of type 'int' with expression of type 'float'", diags[0].message)

    def test_type_mismatch_in_assignment(self):
        source = """
        int main() {
            int x = 10;
            x = false;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Cannot assign type 'bool' to variable 'x' of type 'int'", diags[0].message)

    def test_type_mismatch_in_arithmetic_binary_op(self):
        source = """
        int main() {
            int x = 5 + true;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Binary operator '+' requires numeric operands", diags[0].message)

    def test_modulo_with_non_integer(self):
        source = """
        int main() {
            float f = 5.5;
            int x = f % 2;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Operator '%' requires operands of type 'int'", diags[0].message)

    def test_logical_operator_type_mismatch(self):
        source = """
        int main() {
            bool b = true && 42;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Logical operator '&&' requires 'bool' operands", diags[0].message)

    def test_relational_operator_type_mismatch(self):
        source = """
        int main() {
            bool b = 5 < true;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Relational operator '<' requires numeric operands", diags[0].message)

    def test_equality_operator_type_mismatch(self):
        source = """
        int main() {
            bool b = 10 == true;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Type mismatch in equality operator '=='", diags[0].message)

    def test_unary_operator_type_mismatch(self):
        source = """
        int main() {
            bool b = !10;
            int x = -false;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 2)
        self.assertIn("Logical NOT operator '!' requires 'bool' operand", diags[0].message)
        self.assertIn("Unary operator '-' requires numeric operand", diags[1].message)

    def test_if_and_while_condition_type_mismatch(self):
        source = """
        int main() {
            if (123) {
                print("invalid if condition");
            }
            while ("not a bool") {
                print("invalid while condition");
            }
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 2)
        self.assertIn("Condition expression in 'if' must be of type 'bool'", diags[0].message)
        self.assertIn("Condition expression in 'while' must be of type 'bool'", diags[1].message)

    # ── 4. Wrong Argument Count or Types in Calls ─────────────────────────────

    def test_call_wrong_argument_count_too_few(self):
        source = """
        int add(int a, int b) {
            return a + b;
        }
        int main() {
            int res = add(1);
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Function 'add' expects 2 argument(s), got 1", diags[0].message)

    def test_call_wrong_argument_count_too_many(self):
        source = """
        int add(int a, int b) {
            return a + b;
        }
        int main() {
            int res = add(1, 2, 3);
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Function 'add' expects 2 argument(s), got 3", diags[0].message)

    def test_call_wrong_argument_type(self):
        source = """
        int add(int a, int b) {
            return a + b;
        }
        int main() {
            int res = add(1, true);
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Argument 2 of function 'add' expects type 'int', got 'bool'", diags[0].message)

    def test_call_variable_as_function(self):
        source = """
        int main() {
            int x = 42;
            x();
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("'x' is a variable, not a function", diags[0].message)

    # ── 5. Missing Return & Return Type Mismatches ─────────────────────────────

    def test_missing_return_in_non_void_function(self):
        source = """
        int compute(int a) {
            int b = a + 1;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Missing return statement in non-void function 'compute'", diags[0].message)

    def test_missing_return_when_only_one_branch_returns(self):
        source = """
        int test(int x) {
            if (x > 0) {
                return 1;
            }
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Missing return statement in non-void function 'test'", diags[0].message)

    def test_both_branches_return_is_valid(self):
        source = """
        int abs_val(int x) {
            if (x < 0) {
                return -x;
            } else {
                return x;
            }
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 0)

    def test_void_function_with_return_value(self):
        source = """
        void do_work() {
            return 123;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Void function 'do_work' cannot return a value", diags[0].message)

    def test_non_void_function_with_empty_return(self):
        source = """
        int get_number() {
            return;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Non-void function 'get_number' must return a value of type 'int'", diags[0].message)

    def test_return_type_mismatch(self):
        source = """
        int get_number() {
            return true;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Function 'get_number' expects return type 'int', got 'bool'", diags[0].message)

    def test_return_outside_of_function(self):
        source = """
        return 42;
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("'return' statement outside of function", diags[0].message)

    # ── 6. Use Before Initialization ─────────────────────────────────────────

    def test_use_before_initialization_in_expression(self):
        source = """
        int main() {
            int x;
            int y = x + 1;
            return y;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Variable 'x' used before initialization", diags[0].message)

    def test_self_referential_initialization(self):
        source = """
        int main() {
            int x = x + 1;
            return x;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Variable 'x' used before initialization", diags[0].message)

    def test_valid_post_assignment_usage(self):
        source = """
        int main() {
            int x;
            x = 10;
            int y = x + 5;
            return y;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 0)

    def test_conditional_initialization_partial(self):
        source = """
        int main() {
            int x;
            if (true) {
                x = 10;
            }
            int y = x + 1;
            return y;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Variable 'x' used before initialization", diags[0].message)

    def test_conditional_initialization_both_branches(self):
        source = """
        int main() {
            int x;
            if (true) {
                x = 10;
            } else {
                x = 20;
            }
            int y = x + 1;
            return y;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 0)

    # ── 7. Complete Valid Programs ───────────────────────────────────────────

    def test_valid_recursive_factorial_program(self):
        source = """
        int factorial(int n) {
            if (n <= 1) {
                return 1;
            } else {
                return n * factorial(n - 1);
            }
        }

        int main() {
            int result = factorial(5);
            print(result);
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 0)

    def test_valid_fibonacci_while_loop(self):
        source = """
        int fib(int n) {
            int a = 0;
            int b = 1;
            int i = 0;
            while (i < n) {
                int temp = a + b;
                a = b;
                b = temp;
                i = i + 1;
            }
            return a;
        }

        int main() {
            int ans = fib(10);
            print(ans);
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 0)

    # ── 8. SymbolTable & Advanced Diagnostic Checks ──────────────────────────

    def test_symbol_table_scoping_behavior(self):
        root = SymbolTable(parent=None, name="root")
        v1 = VarSymbol(name="x", var_type="int")
        self.assertTrue(root.define(v1))
        # Cannot redefine in same scope
        v1_dup = VarSymbol(name="x", var_type="float")
        self.assertFalse(root.define(v1_dup))

        # Child scope can lookup parent
        child = SymbolTable(parent=root, name="child")
        self.assertIs(child.lookup("x"), v1)
        self.assertIsNone(child.lookup_current("x"))

        # Child scope can shadow parent
        v2 = VarSymbol(name="x", var_type="float")
        self.assertTrue(child.define(v2))
        self.assertIs(child.lookup("x"), v2)
        self.assertIs(child.lookup_current("x"), v2)
        # Parent still sees original
        self.assertIs(root.lookup("x"), v1)

    def test_diagnostic_formatting(self):
        diag = Diagnostic(message="Test error message", line=12, column=5, severity="error")
        self.assertEqual(str(diag), "[Line 12:5] Semantic Error: Test error message")

    def test_forward_function_call(self):
        source = """
        int main() {
            return helper(42);
        }

        int helper(int val) {
            return val + 1;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 0)

    def test_error_cascading_suppression(self):
        source = """
        int main() {
            int x = missing_var + 1 + 2 * 3;
            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 1)
        self.assertIn("Undeclared variable 'missing_var'", diags[0].message)

    def test_multiple_distinct_diagnostics_collected(self):
        source = """
        int f1() {
            int x = undeclared_var;
            return 0;
        }

        void f2() {
            return 123;
        }

        int f3() {
            int a = 1;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 3)
        messages = [d.message for d in diags]
        self.assertTrue(any("Undeclared variable 'undeclared_var'" in m for m in messages))
        self.assertTrue(any("Void function 'f2' cannot return a value" in m for m in messages))
        self.assertTrue(any("Missing return statement in non-void function 'f3'" in m for m in messages))


    def test_all_six_rules_reported_once(self):
        source = """
        void helper(int a) {}

        int missing_return_func() {
            int x = 1;
        }

        int main() {
            // Rule 1: Redeclaration in same scope
            int dup = 1;
            int dup = 2;

            // Rule 2: Use before initialization
            int uninit;
            int use_uninit = uninit + 1;

            // Rule 3: Undeclared variable
            undeclared_var = 42;

            // Rule 4: Type mismatch in binary operation
            int bad_math = 5 + true;

            // Rule 5: Wrong argument type in call
            helper(true);

            return 0;
        }
        """
        diags = analyze(source)
        self.assertEqual(len(diags), 6)

        messages = [d.message for d in diags]
        # Rule: Missing return in non-void function
        self.assertEqual(sum("Missing return statement in non-void function" in m for m in messages), 1)
        # Rule: Redeclaration in same scope
        self.assertEqual(sum("Redeclaration of variable 'dup' in the same scope" in m for m in messages), 1)
        # Rule: Use before initialization
        self.assertEqual(sum("Variable 'uninit' used before initialization" in m for m in messages), 1)
        # Rule: Undeclared variable
        self.assertEqual(sum("Undeclared variable 'undeclared_var'" in m for m in messages), 1)
        # Rule: Type mismatch in binary operations
        self.assertEqual(sum("Binary operator '+' requires numeric operands" in m for m in messages), 1)
        # Rule: Wrong argument count or types in calls
        self.assertEqual(sum("Argument 1 of function 'helper' expects type 'int', got 'bool'" in m for m in messages), 1)


if __name__ == "__main__":
    unittest.main()
