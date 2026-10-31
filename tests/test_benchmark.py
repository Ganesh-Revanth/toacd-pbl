import csv
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure src/ is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_PROJECT_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from evaluation.benchmark import (
    get_expected_category,
    evaluate_classifier_match,
    run_rule_based_healer,
    run_llm_agent,
    discover_test_cases,
    run_benchmark,
    print_summary_table,
    format_markdown_table,
)


class TestBenchmarkModule(unittest.TestCase):
    """Unit tests for src/evaluation/benchmark.py harness."""

    def test_get_expected_category(self):
        self.assertEqual(get_expected_category("syntax_error.cpp"), "syntax_error")
        self.assertEqual(get_expected_category("missing_header.cpp"), "missing_include")
        self.assertEqual(get_expected_category("tc01_missing_semicolon.cpp"), "syntax_error")
        self.assertEqual(get_expected_category("tc02_undeclared_variable.cpp"), "name_resolution")
        self.assertEqual(get_expected_category("custom_type_mismatch.cpp"), "type_error")

    def test_discover_test_cases(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_a = os.path.join(tmp_dir, "test1.cpp")
            file_b = os.path.join(tmp_dir, "test2.cpp")
            backup = os.path.join(tmp_dir, "test1.cpp.heal_backup")
            other = os.path.join(tmp_dir, "notes.txt")

            for f in (file_a, file_b, backup, other):
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write("// test\n")

            discovered = discover_test_cases(tmp_dir)
            self.assertEqual(len(discovered), 2)
            self.assertIn(file_a, discovered)
            self.assertIn(file_b, discovered)
            self.assertNotIn(backup, discovered)

    def test_evaluate_classifier_match(self):
        mock_classifier = MagicMock()
        mock_classifier.predict.return_value = ("syntax_error", 0.99)

        code_with_syntax_error = "int main() { int x = 10 return 0; }\n"
        with tempfile.NamedTemporaryFile(suffix=".cpp", delete=False) as tf:
            tf.write(code_with_syntax_error.encode("utf-8"))
            temp_path = tf.name

        try:
            with patch("evaluation.benchmark._compile") as mock_compile:
                mock_compile.return_value = ([
                    {"file": temp_path, "line": 1, "column": 25, "type": "error", "message": "expected ';' before 'return'"}
                ], "error")

                exp_cat, pred_cat, is_match = evaluate_classifier_match(
                    code_with_syntax_error,
                    "test_cases/syntax_error.cpp",
                    mock_classifier,
                )
                self.assertEqual(exp_cat, "syntax_error")
                self.assertEqual(pred_cat, "syntax_error")
                self.assertTrue(is_match)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_run_rule_based_healer_already_clean(self):
        mock_classifier = MagicMock()
        clean_code = "#include <iostream>\nint main() { return 0; }\n"

        with patch("evaluation.benchmark._compile") as mock_compile:
            mock_compile.return_value = ([], "")
            result = run_rule_based_healer(clean_code, "clean.cpp", mock_classifier, max_attempts=3)
            self.assertTrue(result["compiled"])
            self.assertEqual(result["attempts"], 0)

    def test_run_rule_based_healer_successful_patch(self):
        mock_classifier = MagicMock()
        err_code = "int main() { int x = 5 return 0; }"
        fixed_code = "int main() { int x = 5; return 0; }"

        with patch("evaluation.benchmark._compile") as mock_compile, \
             patch("evaluation.benchmark.attempt_fix", return_value=fixed_code):
            # First compile returns an error, second compile after fix returns clean
            mock_compile.side_effect = [
                ([{"file": "dummy.cpp", "line": 1, "type": "error", "message": "expected ';'", "category": "syntax_error"}], "err"),
                ([{"file": "dummy.cpp", "line": 1, "type": "error", "message": "expected ';'", "category": "syntax_error"}], "err"),
                ([], ""),
            ]

            result = run_rule_based_healer(err_code, "test.cpp", mock_classifier, max_attempts=3)
            self.assertTrue(result["compiled"])
            self.assertEqual(result["attempts"], 1)

    def test_run_llm_agent(self):
        with patch("evaluation.benchmark.CompilerAgent") as MockAgent:
            mock_inst = MagicMock()
            mock_inst.heal.return_value = {
                "success": True,
                "iterations": 2,
                "tier": "tier_1",
            }
            MockAgent.return_value = mock_inst

            result = run_llm_agent("int main() {}", "test.cpp", max_attempts=3)
            self.assertTrue(result["compiled"])
            self.assertEqual(result["attempts"], 2)

    def test_run_benchmark_offline_creates_csv(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_dir = os.path.join(tmp_dir, "test_cases")
            os.makedirs(test_dir, exist_ok=True)
            test_file = os.path.join(test_dir, "syntax_error.cpp")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("int main() { int x = 10 return 0; }\n")

            out_csv = os.path.join(tmp_dir, "results", "baseline.csv")

            with patch("evaluation.benchmark.ErrorClassifier") as MockClassifier, \
                 patch("evaluation.benchmark._compile", return_value=([], "")):
                mock_clf = MagicMock()
                mock_clf.is_trained.return_value = True
                mock_clf.predict.return_value = ("syntax_error", 1.0)
                MockClassifier.return_value = mock_clf

                res = run_benchmark(
                    test_dir=test_dir,
                    output_csv=out_csv,
                    no_llm=True,
                    max_attempts=3,
                )

                self.assertEqual(len(res), 1)
                self.assertEqual(res[0]["llm_compiled"], "skipped")
                self.assertTrue(os.path.exists(out_csv))

                with open(out_csv, "r", encoding="utf-8") as f:
                    reader = list(csv.DictReader(f))
                    self.assertEqual(len(reader), 1)
                    self.assertIn("rule_compiled", reader[0])
                    self.assertIn("category_matched", reader[0])
                    self.assertEqual(reader[0]["llm_compiled"], "skipped")

    def test_print_summary_table(self):
        mock_results = [
            {
                "file": "test1.cpp",
                "category_matched": "yes",
                "rule_compiled": "yes",
                "rule_attempts": 1,
                "rule_time_sec": 0.05,
                "llm_compiled": "skipped",
                "llm_attempts": 0,
                "llm_time_sec": 0.0,
            }
        ]
        # Verify it runs without error
        print_summary_table(mock_results, no_llm=True)
        print_summary_table(mock_results, no_llm=False)

    def test_format_markdown_table(self):
        healing_mock = [
            {
                "suite": "healing",
                "file": "test_cases/tc01.cpp",
                "expected_category": "syntax_error",
                "category_matched": "yes",
                "rule_compiled": "yes",
                "rule_attempts": 1,
                "rule_time_sec": 0.04,
                "llm_compiled": "yes",
                "llm_attempts": 1,
                "llm_time_sec": 1.25,
            }
        ]

        md = format_markdown_table(healing_mock)
        self.assertIn("# Self-Healing Compiler Benchmark Results", md)
        self.assertIn("## 1. Self-Healing Comparative Evaluation", md)
        self.assertIn("## 2. Aggregate Performance & Verification Summary", md)
        self.assertIn("`tc01.cpp`", md)

    def test_run_benchmark_with_markdown_creates_final_csv(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_dir = os.path.join(tmp_dir, "test_cases")
            os.makedirs(test_dir, exist_ok=True)
            test_file = os.path.join(test_dir, "syntax_error.cpp")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("int main() { int x = 10 return 0; }\n")

            out_csv = os.path.join(tmp_dir, "results", "final.csv")
            out_md = os.path.join(tmp_dir, "results", "benchmark_summary.md")

            with patch("evaluation.benchmark.ErrorClassifier") as MockClassifier, \
                 patch("evaluation.benchmark._compile", return_value=([], "")):
                mock_clf = MagicMock()
                mock_clf.is_trained.return_value = True
                mock_clf.predict.return_value = ("syntax_error", 1.0)
                MockClassifier.return_value = mock_clf

                res = run_benchmark(
                    test_dir=test_dir,
                    output_csv=out_csv,
                    no_llm=True,
                    max_attempts=3,
                    markdown_path=out_md,
                )

                self.assertEqual(len(res), 1)
                self.assertTrue(os.path.exists(out_csv))
                self.assertTrue(os.path.exists(out_md))

                with open(out_csv, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["suite"], "healing")


if __name__ == "__main__":
    unittest.main()
