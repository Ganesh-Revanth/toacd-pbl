"""
Regression tests for miscompilation bugs found by differential testing.

Every program is executed both as raw TAC and as optimized TAC; the two must agree
and must match the output expected from C semantics.
"""

import os
import sys
import unittest

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from core.interpreter import run_ir
from core.ir import c_div, c_mod, generate_ir
from core.lexer import Lexer
from core.optimizer import optimize


def run_both(src):
    ir = generate_ir(src)
    raw = run_ir(ir)
    opt, _ = optimize(ir)
    return raw, run_ir(opt)


class TestRegressions(unittest.TestCase):
    def check(self, src, expected):
        raw, opt = run_both(src)
        self.assertEqual(raw, expected, "raw TAC output")
        self.assertEqual(opt, expected, "optimized TAC output")

    # -- scoping ---------------------------------------------------------------
    def test_inner_scope_shadowing_does_not_clobber_outer(self):
        self.check("int main(){ int x=1; { int x=2; print(x);} print(x); return 0; }", ["2", "1"])

    def test_shadowing_inside_loop(self):
        self.check(
            "int main(){ int i=0; int s=0; while(i<3){ int s2=i; { int s=100; s2=s2+s; } "
            "print(s2); i=i+1;} print(s); return 0; }",
            ["100", "101", "102", "0"],
        )

    def test_user_names_that_look_like_renamed_variables(self):
        self.check(
            "int main(){ int x=1; { int x=2; int x_1=7; print(x); print(x_1);} print(x); return 0; }",
            ["2", "7", "1"],
        )

    def test_user_variable_named_like_compiler_temp(self):
        self.check("int main(){ int t1 = 5; int y = t1 + 1; print(t1); print(y); return 0; }", ["5", "6"])

    # -- globals ---------------------------------------------------------------
    def test_function_can_modify_global(self):
        self.check("int g=10; int f(){ g=g+1; return g; } int main(){ print(f()); print(g); return 0; }", ["11", "11"])

    def test_local_shadowing_a_global_leaves_global_alone(self):
        self.check("int g=10; int f(){ int g=1; g=g+1; return g; } int main(){ print(f()); print(g); return 0; }", ["2", "10"])

    def test_global_not_constant_propagated_across_call(self):
        self.check("int g=1; int f(){ g=5; return 0; } int main(){ int r=f(); print(g); return 0; }", ["5"])

    def test_parameter_shadowing_a_global(self):
        self.check("int g=3; int f(int g){ g=g+1; return g; } int main(){ print(f(10)); print(g); return 0; }", ["11", "3"])

    # -- short-circuit evaluation -----------------------------------------------
    def test_and_short_circuits(self):
        self.check("int f(){ print(99); return 1; } int main(){ bool b = false && f()==1; print(b); return 0; }", ["false"])

    def test_or_short_circuits(self):
        self.check(
            "int f(){ print(99); return 1; } int main(){ bool b = true || f()==1; print(b); "
            "bool c = false || f()==1; print(c); return 0; }",
            ["true", "99", "true"],
        )

    def test_short_circuit_guards_division_by_zero(self):
        self.check("int main(){ int x=0; if(x!=0 && 10/x>1){ print(1);} else {print(2);} return 0; }", ["2"])

    def test_short_circuit_in_loop_condition(self):
        self.check("int main(){ int i=0; while(i<5 && i*i<10){ print(i); i=i+1;} return 0; }", ["0", "1", "2", "3"])

    # -- C integer division / remainder ----------------------------------------
    def test_division_truncates_toward_zero(self):
        self.check(
            "int main(){ print(7/2); print(-7/2); print(7/-2); print(-7/-2); return 0; }",
            ["3", "-3", "-3", "3"],
        )

    def test_remainder_takes_sign_of_dividend(self):
        self.check(
            "int main(){ print(7%3); print(-7%3); print(7%-3); print(-7%-3); return 0; }",
            ["1", "-1", "1", "-1"],
        )

    def test_runtime_division_matches_folded_division(self):
        self.check("int main(){ int a=-7; int b=2; print(a/b); print(a%b); return 0; }", ["-3", "-1"])

    def test_helpers(self):
        self.assertEqual(c_div(-7, 2), -3)
        self.assertEqual(c_mod(-7, 2), -1)
        self.assertEqual(c_div(7.0, 2), 3.5)

    # -- lexer -------------------------------------------------------------------
    def test_block_comments(self):
        self.check("int main(){ /* multi\nline */ int x = 1; /* inline */ print(x); return 0; }", ["1"])

    def test_unterminated_block_comment_is_reported(self):
        lx = Lexer("int main(){ return 0; } /* never closed")
        lx.tokenize()
        self.assertTrue(any("block comment" in e.message for e in lx.errors))

    def test_block_comment_keeps_line_numbers(self):
        toks = Lexer("/* a\nb\nc */ int").tokenize()
        self.assertEqual(toks[0].line, 3)


if __name__ == "__main__":
    unittest.main()
