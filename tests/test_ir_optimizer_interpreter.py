"""
test_ir_optimizer_interpreter.py
--------------------------------
Unit tests for TAC IR Generation, Optimizer Passes, and TAC Interpreter.

Verifies:
  1. Each optimizer pass as a separate function reporting instruction removal count.
  2. Interpreter execution and output capture.
  3. Equivalence test: at least 10 distinct programs produce identical outputs
     before and after optimization.
"""

import os
import sys
import unittest

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from core.ir import Const, Instruction, generate_ir
from core.interpreter import Interpreter, run_ir
from core.optimizer import (
    algebraic_simplification,
    common_subexpression_elimination,
    constant_folding,
    constant_propagation,
    dead_code_elimination,
    optimize,
)


class TestIROptimizerInterpreter(unittest.TestCase):
    """Test suite for TAC IR, individual optimizer passes, and interpreter."""

    # ── 1. Individual Optimizer Passes ────────────────────────────────────────

    def test_pass_constant_folding(self):
        insts = [
            Instruction("+", result="t0", arg1=Const(2), arg2=Const(3)),
            Instruction("*", result="t1", arg1=Const(4), arg2=Const(5)),
            Instruction("!", result="t2", arg1=Const(False)),
            Instruction("PRINT", arg1="t0"),
        ]
        folded, count = constant_folding(insts)
        self.assertEqual(count, 3)
        self.assertEqual(folded[0].op, "ASSIGN")
        self.assertEqual(folded[0].arg1, Const(5))
        self.assertEqual(folded[1].op, "ASSIGN")
        self.assertEqual(folded[1].arg1, Const(20))
        self.assertEqual(folded[2].op, "ASSIGN")
        self.assertEqual(folded[2].arg1, Const(True))

    def test_pass_constant_propagation(self):
        insts = [
            Instruction("ASSIGN", result="x", arg1=Const(10)),
            Instruction("+", result="t0", arg1="x", arg2=Const(5)),
            Instruction("*", result="t1", arg1=Const(2), arg2="x"),
        ]
        propagated, count = constant_propagation(insts)
        self.assertEqual(count, 2)
        self.assertEqual(propagated[1].arg1, Const(10))
        self.assertEqual(propagated[2].arg2, Const(10))

    def test_pass_algebraic_simplification(self):
        insts = [
            Instruction("*", result="t0", arg1="x", arg2=Const(1)),
            Instruction("*", result="t1", arg1=Const(0), arg2="y"),
            Instruction("+", result="t2", arg1=Const(0), arg2="z"),
            Instruction("-", result="t3", arg1="w", arg2=Const(0)),
            Instruction("/", result="t4", arg1="v", arg2=Const(1)),
            Instruction("&&", result="t5", arg1="b", arg2=Const(True)),
            Instruction("||", result="t6", arg1=Const(False), arg2="b"),
        ]
        simplified, count = algebraic_simplification(insts)
        self.assertEqual(count, 7)
        self.assertEqual(simplified[0], Instruction("ASSIGN", result="t0", arg1="x"))
        self.assertEqual(simplified[1], Instruction("ASSIGN", result="t1", arg1=Const(0)))
        self.assertEqual(simplified[2], Instruction("ASSIGN", result="t2", arg1="z"))
        self.assertEqual(simplified[3], Instruction("ASSIGN", result="t3", arg1="w"))
        self.assertEqual(simplified[4], Instruction("ASSIGN", result="t4", arg1="v"))
        self.assertEqual(simplified[5], Instruction("ASSIGN", result="t5", arg1="b"))
        self.assertEqual(simplified[6], Instruction("ASSIGN", result="t6", arg1="b"))

    def test_pass_common_subexpression_elimination(self):
        insts = [
            Instruction("+", result="t0", arg1="a", arg2="b"),
            Instruction("+", result="t1", arg1="a", arg2="b"),      # Duplicate
            Instruction("+", result="t2", arg1="b", arg2="a"),      # Commutative duplicate
            Instruction("PRINT", arg1="t0"),
            Instruction("PRINT", arg1="t1"),
            Instruction("PRINT", arg1="t2"),
        ]
        cse_insts, count = common_subexpression_elimination(insts)
        self.assertEqual(count, 2)
        self.assertEqual(cse_insts[1], Instruction("ASSIGN", result="t1", arg1="t0"))
        self.assertEqual(cse_insts[2], Instruction("ASSIGN", result="t2", arg1="t0"))

    def test_pass_dead_code_elimination(self):
        insts = [
            Instruction("ASSIGN", result="unused", arg1=Const(42)),
            Instruction("+", result="dead_calc", arg1=Const(1), arg2=Const(2)),
            Instruction("ASSIGN", result="x", arg1=Const(10)),
            Instruction("PRINT", arg1="x"),
            Instruction("RETURN"),
            Instruction("PRINT", arg1=Const(999)),                 # Unreachable!
        ]
        dce_insts, count = dead_code_elimination(insts)
        self.assertGreaterEqual(count, 3)
        res_names = [i.result for i in dce_insts if i.result]
        self.assertNotIn("unused", res_names)
        self.assertNotIn("dead_calc", res_names)
        self.assertEqual(len([i for i in dce_insts if i.op == "PRINT"]), 1)

    # ── 2. Equivalence Suite: 10 Programs (Before vs After Optimization) ─────

    def _verify_program_equivalence(self, source: str, expected_output: list[str]) -> None:
        """Helper to run a program unoptimized vs optimized and assert output equivalence."""
        ir_unopt = generate_ir(source)
        out_unopt = Interpreter(ir_unopt).run()

        ir_opt, stats = optimize(ir_unopt)
        out_opt = Interpreter(ir_opt).run()

        self.assertEqual(out_unopt, expected_output)
        self.assertEqual(out_opt, expected_output)
        self.assertLessEqual(len(ir_opt), len(ir_unopt))

    def test_prog_1_constant_arithmetic_folding(self):
        source = """
        int main() {
            int x = (2 + 3) * 4 + (10 - 2) / 2;
            print(x);
            return 0;
        }
        """
        # (5)*4 + 8/2 = 20 + 4 = 24
        self._verify_program_equivalence(source, ["24"])

    def test_prog_2_algebraic_identities(self):
        source = """
        int main() {
            int x = 7;
            int a = x * 1;
            int b = x + 0;
            int c = x * 0;
            int d = x - 0;
            int e = x / 1;
            print(a);
            print(b);
            print(c);
            print(d);
            print(e);
            return 0;
        }
        """
        self._verify_program_equivalence(source, ["7", "7", "0", "7", "7"])

    def test_prog_3_common_subexpression_elimination(self):
        source = """
        int main() {
            int a = 3;
            int b = 4;
            int x = a + b;
            int y = a + b;
            int z = b + a;
            print(x);
            print(y);
            print(z);
            return 0;
        }
        """
        self._verify_program_equivalence(source, ["7", "7", "7"])

    def test_prog_4_dead_code_elimination(self):
        source = """
        int main() {
            int unused1 = 100 * 200;
            int unused2 = 50 + 10;
            int live = 42;
            print(live);
            return 0;
        }
        """
        self._verify_program_equivalence(source, ["42"])

    def test_prog_5_while_loop_counter_accumulator(self):
        source = """
        int main() {
            int i = 1;
            int sum = 0;
            while (i <= 5) {
                sum = sum + i;
                i = i + 1;
            }
            print(sum);
            return 0;
        }
        """
        # sum 1..5 = 15
        self._verify_program_equivalence(source, ["15"])

    def test_prog_6_if_else_conditionals(self):
        source = """
        int check(int val) {
            if (val > 10) {
                return 100;
            } else {
                return 200;
            }
        }

        int main() {
            print(check(15));
            print(check(5));
            return 0;
        }
        """
        self._verify_program_equivalence(source, ["100", "200"])

    def test_prog_7_recursive_factorial(self):
        source = """
        int fact(int n) {
            if (n <= 1) {
                return 1;
            }
            return n * fact(n - 1);
        }

        int main() {
            print(fact(6));
            return 0;
        }
        """
        # 6! = 720
        self._verify_program_equivalence(source, ["720"])

    def test_prog_8_iterative_fibonacci(self):
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
            print(fib(8));
            return 0;
        }
        """
        # Fib(8) = 21
        self._verify_program_equivalence(source, ["21"])

    def test_prog_9_multi_function_calls(self):
        source = """
        int square(int x) {
            return x * x;
        }

        int sum_squares(int a, int b) {
            return square(a) + square(b);
        }

        int main() {
            print(sum_squares(3, 4));
            return 0;
        }
        """
        # 3^2 + 4^2 = 25
        self._verify_program_equivalence(source, ["25"])

    def test_prog_10_complex_boolean_logic(self):
        source = """
        int main() {
            bool a = true;
            bool b = false;
            bool r1 = a && !b;
            bool r2 = b || (a && true);
            bool r3 = (10 > 5) && (3 == 3);
            print(r1);
            print(r2);
            print(r3);
            return 0;
        }
        """
        self._verify_program_equivalence(source, ["true", "true", "true"])

    def test_prog_11_nested_loops_and_modulo(self):
        source = """
        int main() {
            int count = 0;
            int i = 1;
            while (i <= 10) {
                if (i % 2 == 0) {
                    count = count + 1;
                }
                i = i + 1;
            }
            print(count);
            return 0;
        }
        """
        # Even numbers in 1..10 = 5
        self._verify_program_equivalence(source, ["5"])

    def test_ten_programs_combined_equivalence_suite(self):
        """Explicit single test executing 10 distinct programs verifying exact equivalence."""
        test_programs = [
            # 1. Arithmetic chain
            ("int main() { int a = 10; int b = 20; print(a + b * 2); return 0; }", ["50"]),
            # 2. Algebraic simplification & folding
            ("int main() { int x = 15; int y = x * 1 + 0; print(y); return 0; }", ["15"]),
            # 3. Dead computation
            ("int main() { int dead = 100 * 50; int alive = 99; print(alive); return 0; }", ["99"]),
            # 4. CSE
            ("int main() { int x = 5; int y = 6; int a = x * y; int b = y * x; print(a); print(b); return 0; }", ["30", "30"]),
            # 5. While loop sum
            ("int main() { int s = 0; int i = 1; while (i <= 4) { s = s + i; i = i + 1; } print(s); return 0; }", ["10"]),
            # 6. If branch
            ("int main() { int a = 7; if (a < 10) { print(1); } else { print(2); } return 0; }", ["1"]),
            # 7. Factorial
            ("int f(int n) { if (n <= 1) return 1; return n * f(n - 1); } int main() { print(f(4)); return 0; }", ["24"]),
            # 8. Fibonacci
            ("int fib(int n) { int a = 0; int b = 1; int i = 0; while (i < n) { int t = a + b; a = b; b = t; i = i + 1; } return a; } int main() { print(fib(6)); return 0; }", ["8"]),
            # 9. Function calling function
            ("int inc(int x) { return x + 1; } int double_inc(int x) { return inc(inc(x)); } int main() { print(double_inc(5)); return 0; }", ["7"]),
            # 10. Boolean logic
            ("int main() { bool flag = (5 > 2) && (!false); print(flag); return 0; }", ["true"]),
        ]

        self.assertGreaterEqual(len(test_programs), 10)
        for idx, (prog_source, expected) in enumerate(test_programs, 1):
            with self.subTest(program_index=idx):
                self._verify_program_equivalence(prog_source, expected)


if __name__ == "__main__":
    unittest.main()


def test_interpreter_rejects_unknown_opcode():
    """An unknown TAC op must raise, otherwise a bogus AI patch could slip past verification."""
    import pytest
    from core.ir import Instruction, generate_ir
    from core.interpreter import run_ir

    ir = generate_ir("int main() { int a = 5; print(a); return 0; }")
    ir.insert(1, Instruction(op="FROBNICATE", result="a"))
    with pytest.raises(RuntimeError, match="Unknown TAC instruction"):
        run_ir(ir)
