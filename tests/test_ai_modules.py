"""
test_ai_modules.py
------------------
Comprehensive unit tests for the AI compiler modules:
  1. schema_utils.py (JSON extraction, schema validation, 1-retry behavior, fallback)
  2. phase_explainer.py (compiler pipeline explanation, schema validation)
  3. ai_optimizer.py (TAC optimization suggestions, equivalence check via interpreter, logging)
  4. bug_detector.py (logic bug detection, AST line number filtering, pruning hallucinated lines)

All tests run completely offline and pass with LLM_MOCK=1.
"""

import json
import os
import sys
import unittest

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Force offline mock mode for all tests
os.environ["LLM_MOCK"] = "1"

from ai.ai_optimizer import (
    AI_OPTIMIZER_SCHEMA,
    ai_optimize_ir,
    dict_to_instruction,
    instruction_to_dict,
    optimize_program_with_ai,
)
from ai.bug_detector import (
    BUG_DETECTOR_SCHEMA,
    collect_ast_lines,
    detect_bugs,
)
from ai.llm_client import LLMClient
from ai.phase_explainer import (
    PHASE_EXPLAINER_SCHEMA,
    create_fallback_explanation,
    explain_compilation,
    explain_phases,
)
from ai.schema_utils import extract_json_from_text, query_structured_json
from core.ir import Const, Instruction, generate_ir
from core.interpreter import Interpreter
from core.lexer import Lexer
from core.parser import Parser
from core.semantic import SemanticAnalyzer


class TestSchemaUtils(unittest.TestCase):
    """Tests for schema validation, json extraction, retries, and fallbacks."""

    def test_extract_json_markdown_fences(self):
        text = "Here is the response:\n```json\n{\"foo\": 1, \"bar\": \"hello\"}\n```\nHope that helps!"
        res = extract_json_from_text(text)
        self.assertIsNotNone(res)
        self.assertEqual(res, {"foo": 1, "bar": "hello"})

    def test_extract_json_bare_curly_braces(self):
        text = "Prefix commentary {\"status\": \"ok\", \"count\": 42} suffix commentary"
        res = extract_json_from_text(text)
        self.assertIsNotNone(res)
        self.assertEqual(res, {"status": "ok", "count": 42})

    def test_extract_json_invalid(self):
        text = "No json here, just plain words."
        self.assertIsNone(extract_json_from_text(text))

    def test_query_structured_json_success_first_try(self):
        client = LLMClient(mock_mode=True)
        schema = {
            "type": "object",
            "properties": {"val": {"type": "integer"}},
            "required": ["val"],
        }
        client.provider.register_response("TEST_REQ", '{"val": 99}')

        data = query_structured_json(
            client=client,
            system_prompt="system",
            user_prompt="TEST_REQ",
            schema=schema,
            fallback_factory=lambda: {"val": -1},
        )
        self.assertEqual(data, {"val": 99})

    def test_query_structured_json_retry_success(self):
        """First response fails schema, retry provides valid response."""
        client = LLMClient(mock_mode=True)
        schema = {
            "type": "object",
            "properties": {"score": {"type": "number"}},
            "required": ["score"],
        }

        attempts = 0

        def custom_generate(messages, temperature=0.1, timeout=30.0):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return '{"wrong_key": "not a score"}'
            return '{"score": 98.5}'

        client.provider.generate = custom_generate

        data = query_structured_json(
            client=client,
            system_prompt="sys",
            user_prompt="prompt",
            schema=schema,
            fallback_factory=lambda: {"score": 0.0},
        )
        self.assertEqual(attempts, 2)
        self.assertEqual(data, {"score": 98.5})

    def test_query_structured_json_fallback_after_retry_failure(self):
        """Both first try and retry fail -> returns fallback_factory()."""
        client = LLMClient(mock_mode=True)
        schema = {
            "type": "object",
            "properties": {"val": {"type": "integer"}},
            "required": ["val"],
        }

        # Returns invalid JSON every time
        client.provider.register_response("FAIL_REQ", "Invalid gibberish without json")

        fallback_called = False

        def fallback():
            nonlocal fallback_called
            fallback_called = True
            return {"val": 0, "fallback": True}

        data = query_structured_json(
            client=client,
            system_prompt="sys",
            user_prompt="FAIL_REQ",
            schema=schema,
            fallback_factory=fallback,
        )
        self.assertTrue(fallback_called)
        self.assertEqual(data, {"val": 0, "fallback": True})


class TestPhaseExplainer(unittest.TestCase):
    """Tests for compiler phase explainer module."""

    def test_explain_phases_fallback(self):
        source = (
            "int main() {\n"
            "    int a = 10;\n"
            "    int b = 20;\n"
            "    print(a + b);\n"
            "    return 0;\n"
            "}\n"
        )
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        analyzer = SemanticAnalyzer()
        analyzer.analyze(ast)
        ir = generate_ir(ast)

        explanation = create_fallback_explanation(source, tokens, ast, analyzer.global_scope, ir)
        self.assertIn("program_summary", explanation)
        self.assertIn("lexical_analysis", explanation["phases"])
        self.assertIn("syntax_analysis", explanation["phases"])
        self.assertIn("semantic_analysis", explanation["phases"])
        self.assertIn("ir_generation", explanation["phases"])

        self.assertGreater(explanation["phases"]["lexical_analysis"]["token_count"], 0)
        self.assertGreater(explanation["phases"]["ir_generation"]["instruction_count"], 0)

        # Confirm fallback strictly conforms to schema
        import jsonschema
        jsonschema.validate(instance=explanation, schema=PHASE_EXPLAINER_SCHEMA)

    def test_explain_compilation_with_mock(self):
        source = (
            "int main() {\n"
            "    int x = 5;\n"
            "    print(x * 2);\n"
            "    return 0;\n"
            "}\n"
        )
        client = LLMClient(mock_mode=True)
        res = explain_compilation(source, client=client)

        self.assertIn("program_summary", res)
        self.assertIn("phases", res)
        self.assertIn("lexical_analysis", res["phases"])
        self.assertIn("ir_generation", res["phases"])
        self.assertIsInstance(res["phases"]["ir_generation"]["instruction_count"], int)


class TestAIOptimizer(unittest.TestCase):
    """Tests for AI TAC Optimizer with equivalence verification."""

    def setUp(self):
        self.client = LLMClient(mock_mode=True)

    def test_instruction_serialization_roundtrip(self):
        inst = Instruction("+", result="t0", arg1="x", arg2=Const(10))
        d = instruction_to_dict(inst)
        self.assertEqual(d["op"], "+")
        self.assertEqual(d["result"], "t0")
        self.assertEqual(d["arg1"], "x")
        self.assertEqual(d["arg2"], 10)

        restored = dict_to_instruction(d)
        self.assertEqual(restored.op, "+")
        self.assertEqual(restored.result, "t0")
        self.assertEqual(restored.arg1, "x")
        self.assertEqual(restored.arg2, Const(10))

    def test_accept_equivalent_optimization_suggestion(self):
        """
        Baseline IR prints 30.
        Suggestion replaces constant addition '10 + 20' with direct '30'.
        Interpreter produces identical output ['30'], so it must be ACCEPTED.
        """
        # Baseline TAC:
        # 0: t0 = 10 + 20
        # 1: print t0
        # 2: halt
        ir = [
            Instruction("+", result="t0", arg1=Const(10), arg2=Const(20)),
            Instruction("PRINT", arg1="t0"),
            Instruction("HALT"),
        ]

        # Canned response proposing to fold t0 = 30
        canned_response = json.dumps({
            "analysis": "Constant folding for 10 + 20 into 30.",
            "suggestions": [
                {
                    "suggestion_id": "opt_fold_1",
                    "description": "Precompute 10 + 20 = 30",
                    "transformation_type": "constant_folding",
                    "target_indices": [0],
                    "replacement_instructions": [
                        {"op": "ASSIGN", "result": "t0", "arg1": 30, "arg2": None}
                    ],
                }
            ],
        })
        self.client.provider.register_response("OPTIMIZE_TAC_IR", canned_response)

        res = ai_optimize_ir(ir, client=self.client)

        self.assertTrue(res["equivalence_verified"])
        self.assertEqual(len(res["accepted_suggestions"]), 1)
        self.assertEqual(len(res["rejected_suggestions"]), 0)
        self.assertEqual(res["accepted_suggestions"][0]["suggestion_id"], "opt_fold_1")

        # Verify optimized IR produces exact same output ['30']
        out = Interpreter(res["optimized_ir"]).run()
        self.assertEqual(out, ["30"])

    def test_reject_output_altering_suggestion(self):
        """
        Baseline prints 30.
        Buggy AI suggestion replaces '10 + 20' with '999'.
        Interpreter output changes to ['999'], so it must be REJECTED.
        """
        ir = [
            Instruction("+", result="t0", arg1=Const(10), arg2=Const(20)),
            Instruction("PRINT", arg1="t0"),
            Instruction("HALT"),
        ]

        canned_response = json.dumps({
            "analysis": "Erroneous modification changing output.",
            "suggestions": [
                {
                    "suggestion_id": "bad_opt_1",
                    "description": "Erroneously assign 999 to t0",
                    "transformation_type": "broken_simplification",
                    "target_indices": [0],
                    "replacement_instructions": [
                        {"op": "ASSIGN", "result": "t0", "arg1": 999, "arg2": None}
                    ],
                }
            ],
        })
        self.client.provider.register_response("OPTIMIZE_TAC_IR", canned_response)

        res = ai_optimize_ir(ir, client=self.client)

        self.assertEqual(len(res["accepted_suggestions"]), 0)
        self.assertEqual(len(res["rejected_suggestions"]), 1)
        rejected = res["rejected_suggestions"][0]
        self.assertEqual(rejected["suggestion_id"], "bad_opt_1")
        self.assertIn("Output mismatch", rejected["reason"])

        # IR should remain unchanged
        self.assertEqual(len(res["optimized_ir"]), len(ir))
        out = Interpreter(res["optimized_ir"]).run()
        self.assertEqual(out, ["30"])

    def test_reject_out_of_bounds_target_index(self):
        """Suggestion specifies a non-existent instruction index -> rejected."""
        ir = [
            Instruction("ASSIGN", result="x", arg1=Const(1)),
            Instruction("PRINT", arg1="x"),
            Instruction("HALT"),
        ]

        canned_response = json.dumps({
            "analysis": "Invalid index suggestion",
            "suggestions": [
                {
                    "suggestion_id": "bad_idx",
                    "description": "Invalid index 999",
                    "transformation_type": "invalid_index",
                    "target_indices": [999],
                    "replacement_instructions": [],
                }
            ],
        })
        self.client.provider.register_response("OPTIMIZE_TAC_IR", canned_response)

        res = ai_optimize_ir(ir, client=self.client)
        self.assertEqual(len(res["accepted_suggestions"]), 0)
        self.assertEqual(len(res["rejected_suggestions"]), 1)
        self.assertIn("out of bounds", res["rejected_suggestions"][0]["reason"])

    def test_reject_runtime_crash_suggestion(self):
        """Suggestion introduces division by zero -> rejected."""
        ir = [
            Instruction("ASSIGN", result="x", arg1=Const(10)),
            Instruction("PRINT", arg1="x"),
            Instruction("HALT"),
        ]

        canned_response = json.dumps({
            "analysis": "Crash suggestion",
            "suggestions": [
                {
                    "suggestion_id": "div_zero",
                    "description": "Divide by zero",
                    "transformation_type": "crash",
                    "target_indices": [0],
                    "replacement_instructions": [
                        {"op": "/", "result": "x", "arg1": 10, "arg2": 0}
                    ],
                }
            ],
        })
        self.client.provider.register_response("OPTIMIZE_TAC_IR", canned_response)

        res = ai_optimize_ir(ir, client=self.client)
        self.assertEqual(len(res["accepted_suggestions"]), 0)
        self.assertEqual(len(res["rejected_suggestions"]), 1)
        self.assertIn("runtime error", res["rejected_suggestions"][0]["reason"].lower())

    def test_optimize_program_end_to_end(self):
        code = (
            "int main() {\n"
            "    int a = 100;\n"
            "    print(a);\n"
            "    return 0;\n"
            "}\n"
        )
        res = optimize_program_with_ai(code, client=self.client)
        self.assertTrue(res["equivalence_verified"])
        self.assertIsInstance(res["optimized_ir"], list)

    def test_sequential_multiple_suggestions(self):
        """
        Tests handling multiple suggestions in sequence:
          - Sugg 1 (valid): constant fold 10 + 20 -> 30 (ACCEPTED)
          - Sugg 2 (invalid): change 30 to 99 (REJECTED due to mismatch)
          - Sugg 3 (valid): dead code elimination of unused assignment (ACCEPTED)
        """
        ir = [
            Instruction("+", result="t0", arg1=Const(10), arg2=Const(20)),  # 0
            Instruction("ASSIGN", result="unused", arg1=Const(5)),          # 1
            Instruction("PRINT", arg1="t0"),                                # 2
            Instruction("HALT"),                                            # 3
        ]

        canned = json.dumps({
            "analysis": "Multi-step optimization",
            "suggestions": [
                {
                    "suggestion_id": "opt_1",
                    "description": "Fold constant addition",
                    "transformation_type": "constant_folding",
                    "target_indices": [0],
                    "replacement_instructions": [
                        {"op": "ASSIGN", "result": "t0", "arg1": 30, "arg2": None}
                    ],
                },
                {
                    "suggestion_id": "opt_2",
                    "description": "Alter output to 99",
                    "transformation_type": "corrupt",
                    "target_indices": [0],
                    "replacement_instructions": [
                        {"op": "ASSIGN", "result": "t0", "arg1": 99, "arg2": None}
                    ],
                },
                {
                    "suggestion_id": "opt_3",
                    "description": "Remove unused assignment",
                    "transformation_type": "dead_code_elimination",
                    "target_indices": [1],
                    "replacement_instructions": [],
                },
            ],
        })
        self.client.provider.register_response("OPTIMIZE_TAC_IR", canned)

        res = ai_optimize_ir(ir, client=self.client)

        self.assertEqual(len(res["accepted_suggestions"]), 2)
        self.assertEqual(len(res["rejected_suggestions"]), 1)
        self.assertEqual(res["accepted_suggestions"][0]["suggestion_id"], "opt_1")
        self.assertEqual(res["rejected_suggestions"][0]["suggestion_id"], "opt_2")
        self.assertEqual(res["accepted_suggestions"][1]["suggestion_id"], "opt_3")

        # Output remains 30
        out = Interpreter(res["optimized_ir"]).run()
        self.assertEqual(out, ["30"])
        # Original length 4, opt_1 replaces 1 with 1, opt_3 removes 1 -> length 3
        self.assertEqual(len(res["optimized_ir"]), 3)

    def test_ai_optimizer_fallback_on_invalid_output(self):
        """When LLM returns broken JSON, falls back gracefully with 0 suggestions."""
        ir = [
            Instruction("ASSIGN", result="x", arg1=Const(42)),
            Instruction("PRINT", arg1="x"),
            Instruction("HALT"),
        ]
        self.client.provider.register_response("OPTIMIZE_TAC_IR", "Not JSON at all")

        res = ai_optimize_ir(ir, client=self.client)
        self.assertTrue(res["equivalence_verified"])
        self.assertEqual(len(res["accepted_suggestions"]), 0)
        self.assertEqual(len(res["rejected_suggestions"]), 0)
        self.assertIn("fallback", res["analysis"].lower())


class TestBugDetector(unittest.TestCase):
    """Tests for Bug Detector and ground-truth AST line validation."""

    def setUp(self):
        self.client = LLMClient(mock_mode=True)

    def test_collect_ast_lines(self):
        code = (
            "int main() {\n"       # line 1
            "    int i = 0;\n"     # line 2
            "    while (i < 10) {\n"# line 3
            "        i = i + 1;\n" # line 4
            "    }\n"              # line 5
            "    return 0;\n"      # line 6
            "}\n"
        )
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        lines = collect_ast_lines(ast)
        self.assertIn(1, lines)
        self.assertIn(2, lines)
        self.assertIn(3, lines)
        self.assertIn(4, lines)
        self.assertIn(6, lines)
        self.assertNotIn(99, lines)
        self.assertNotIn(0, lines)

    def test_filter_hallucinated_line_numbers(self):
        """
        LLM returns 3 findings:
        - Line 3 (real loop in AST) -> KEPT
        - Line 999 (hallucinated line) -> DISCARDED
        - Line -5 (invalid line) -> DISCARDED
        """
        code = (
            "int main() {\n"
            "    int count = 0;\n"
            "    while (count < 10) {\n"
            "        count = count + 1;\n"
            "    }\n"
            "    return 0;\n"
            "}\n"
        )

        canned_response = json.dumps({
            "summary": "Boundary inspection",
            "bugs": [
                {
                    "line": 3,
                    "category": "off_by_one",
                    "severity": "medium",
                    "description": "Check if loop bound should be <= 10",
                    "fix_suggestion": "Verify inclusive vs exclusive termination.",
                },
                {
                    "line": 999,
                    "category": "unreachable_code",
                    "severity": "low",
                    "description": "Hallucinated dead code on non-existent line 999",
                    "fix_suggestion": "Remove fake line.",
                },
                {
                    "line": -5,
                    "category": "infinite_loop",
                    "severity": "high",
                    "description": "Invalid negative line number bug",
                    "fix_suggestion": "N/A",
                },
            ],
        })
        self.client.provider.register_response("DETECT_LOGIC_BUGS", canned_response)

        res = detect_bugs(code, client=self.client)

        self.assertEqual(res["raw_bug_count"], 3)
        self.assertEqual(res["valid_bug_count"], 1)
        self.assertEqual(res["discarded_bug_count"], 2)

        # Confirm the single valid bug is on line 3
        valid_bug = res["bugs"][0]
        self.assertEqual(valid_bug["line"], 3)
        self.assertEqual(valid_bug["category"], "off_by_one")

        # Confirm the discarded bugs have documented reasons
        discarded_lines = [d["bug"]["line"] for d in res["discarded_bugs"]]
        self.assertIn(999, discarded_lines)
        self.assertIn(-5, discarded_lines)

    def test_bug_detector_fallback_on_schema_failure(self):
        code = "int main() { return 0; }"
        self.client.provider.register_response("DETECT_LOGIC_BUGS", "Invalid non-json response")

        res = detect_bugs(code, client=self.client)
        self.assertIn("fallback", res["summary"].lower())
        self.assertEqual(res["bugs"], [])
        self.assertEqual(res["valid_bug_count"], 0)

    def test_bug_detector_all_categories_and_schema_validation(self):
        """Test reporting across all categories conforming to schema."""
        import jsonschema

        code = (
            "int helper() {\n"     # line 1
            "    return 42;\n"     # line 2
            "}\n"
            "int main() {\n"       # line 4
            "    int a = 0;\n"     # line 5
            "    while (a < 5) {\n"# line 6
            "        a = a + 1;\n" # line 7
            "    }\n"
            "    return 0;\n"      # line 9
            "    print(a);\n"      # line 10 (unreachable)
            "}\n"
        )
        canned = json.dumps({
            "summary": "Multi-category bug analysis",
            "bugs": [
                {
                    "line": 6,
                    "category": "infinite_loop",
                    "severity": "high",
                    "description": "Risk of loop non-termination",
                    "fix_suggestion": "Ensure loop variant decreases.",
                },
                {
                    "line": 10,
                    "category": "unreachable_code",
                    "severity": "low",
                    "description": "Code follows unconditional return statement.",
                    "fix_suggestion": "Move print before return or delete.",
                },
                {
                    "line": 6,
                    "category": "off_by_one",
                    "severity": "medium",
                    "description": "Upper bound off-by-one fencepost error.",
                    "fix_suggestion": "Verify < vs <=.",
                },
                {
                    "line": 5,
                    "category": "other",
                    "severity": "warning",
                    "description": "Style suggestion for declaration.",
                    "fix_suggestion": "Consider const.",
                },
            ],
        })
        self.client.provider.register_response("DETECT_LOGIC_BUGS", canned)

        res = detect_bugs(code, client=self.client)
        self.assertEqual(res["valid_bug_count"], 4)
        self.assertEqual(res["discarded_bug_count"], 0)

        # Validate structured bugs strictly against schema
        jsonschema.validate(
            instance={"summary": res["summary"], "bugs": res["bugs"]},
            schema=BUG_DETECTOR_SCHEMA,
        )


if __name__ == "__main__":
    unittest.main()
