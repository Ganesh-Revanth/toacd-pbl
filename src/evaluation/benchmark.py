"""
benchmark.py
------------
Comparative evaluation benchmark harness for the Green Self-Healing Compiler.

Evaluates each C++ test fixture in test_cases/:
  (a) Rule-based healer (heal_loop with auto_healer heuristics only) up to 3 attempts.
  (b) Autonomous Gemini Agent (CompilerAgent) up to 3 attempts (skippable via --no-llm).

Records:
  - Compiled successfully (yes/no)
  - Attempts used
  - Wall time (seconds)
  - Whether error category matched classifier prediction (yes/no)

Outputs:
  - Formatted results written to results/baseline.csv
  - Formatted ASCII summary table printed to stdout
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
import time
import warnings
from typing import Dict, List, Optional, Tuple, Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Suppress sklearn unpickling warnings
warnings.filterwarnings("ignore")

# Ensure src/ is on sys.path
_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.abspath(os.path.join(_EVAL_DIR, ".."))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SRC_DIR, ".."))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from heal_loop import _compile, _pre_scan, _classify_errors, _pick_fix_target
from auto_healer import attempt_fix
from error_classifier import ErrorClassifier
from build_dataset_from_tests import FILE_LABELS
from agentic_compiler import CompilerAgent


MINI_LABELS: Dict[str, str] = {
    "tc01_missing_semicolon.cpp": "syntax_error",
    "tc02_undeclared_variable.cpp": "name_resolution",
    "tc03_missing_include.cpp": "missing_include",
    "tc04_uninitialized_variable.cpp": "unused_variable",
    "tc05_missing_closing_brace.cpp": "syntax_error",
    "tc06_wrong_stream_operator.cpp": "syntax_error",
    "tc07_keyword_typo.cpp": "syntax_error",
    "tc08_integer_overflow.cpp": "other",
    "tc09_division_by_zero.cpp": "other",
    "tc10_buffer_overflow_gets.cpp": "other",
    "tc11_command_injection.cpp": "other",
    "tc12_memory_leak.cpp": "other",
    "tc13_use_after_free.cpp": "other",
    "tc14_format_string_vuln.cpp": "other",
    "tc15_combined_errors_and_threats.cpp": "syntax_error",
    "tc16_redefinition_double_free.cpp": "redefinition",
}


def get_expected_category(file_path: str) -> Optional[str]:
    """Look up ground-truth category by filename or fallback to heuristic."""
    base_name = os.path.basename(file_path)
    if base_name in FILE_LABELS:
        return FILE_LABELS[base_name]
    if base_name in MINI_LABELS:
        return MINI_LABELS[base_name]

    lower = base_name.lower()
    if "syntax" in lower or "semicolon" in lower or "brace" in lower:
        return "syntax_error"
    if "undeclared" in lower or "name" in lower:
        return "name_resolution"
    if "include" in lower or "header" in lower:
        return "missing_include"
    if "type" in lower or "cast" in lower or "operand" in lower:
        return "type_error"
    if "return" in lower:
        return "return_type_error"
    if "redef" in lower:
        return "redefinition"
    return "other"


def evaluate_classifier_match(
    source_code: str,
    file_path: str,
    classifier: ErrorClassifier,
) -> Tuple[Optional[str], str, bool]:
    """
    Predict error category for the first compile diagnostic and check match
    against ground truth expected category.
    Returns: (expected_category, predicted_category, is_match)
    """
    expected_cat = get_expected_category(file_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = os.path.join(tmp_dir, os.path.basename(file_path))
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(source_code)

        errors, _ = _compile(tmp_file)
        pre_errors = _pre_scan(source_code)
        all_diag = pre_errors + errors

    first_err = next((e for e in all_diag if e.get("type") == "error"), None)
    if first_err is None and all_diag:
        first_err = all_diag[0]

    if first_err:
        pred_cat, _ = classifier.predict(first_err.get("message", ""))
        pred_cat = pred_cat or "other"
        is_match = (expected_cat is not None and pred_cat.lower() == expected_cat.lower())
        return expected_cat, pred_cat, is_match

    # Clean compilation (no errors/warnings)
    is_match = (expected_cat is None or expected_cat == "clean")
    return expected_cat, "clean", is_match


def run_rule_based_healer(
    source_code: str,
    file_path: str,
    classifier: ErrorClassifier,
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """
    Run rule-based healer (heal_loop logic + auto_healer heuristics only)
    up to max_attempts. Runs in an isolated temp directory to protect original files.
    """
    start_time = time.perf_counter()
    current_source = source_code

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = os.path.join(tmp_dir, os.path.basename(file_path))
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(current_source)

        # Initial check
        errors, _ = _compile(tmp_file)
        pre_errors = _pre_scan(current_source)
        all_initial = pre_errors + errors
        if not any(e.get("type") == "error" for e in all_initial):
            return {
                "compiled": True,
                "attempts": 0,
                "time_sec": round(time.perf_counter() - start_time, 3),
            }

        skipped_keys = set()
        attempts_used = 0

        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            errors, _ = _compile(tmp_file)
            pre_errors = _pre_scan(current_source)
            all_errors = pre_errors + errors

            hard_errors = [e for e in all_errors if e.get("type") == "error"]
            if not hard_errors:
                return {
                    "compiled": True,
                    "attempts": attempts_used,
                    "time_sec": round(time.perf_counter() - start_time, 3),
                }

            _classify_errors(all_errors, classifier)
            target = _pick_fix_target(all_errors, skipped_keys)
            if target is None:
                break

            error_key = (target.get("file"), target.get("line"), target.get("message"))
            patched = attempt_fix(current_source, target)
            if patched is None or patched == current_source:
                skipped_keys.add(error_key)
                continue

            current_source = patched
            skipped_keys.clear()
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(current_source)

            # Re-verify compilation after patch
            check_errors, _ = _compile(tmp_file)
            check_pre = _pre_scan(current_source)
            if not any(e.get("type") == "error" for e in check_pre + check_errors):
                return {
                    "compiled": True,
                    "attempts": attempts_used,
                    "time_sec": round(time.perf_counter() - start_time, 3),
                }

        return {
            "compiled": False,
            "attempts": attempts_used,
            "time_sec": round(time.perf_counter() - start_time, 3),
        }


def run_llm_agent(
    source_code: str,
    file_path: str,
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """Run autonomous Gemini compiler agent up to max_attempts."""
    start_time = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = os.path.join(tmp_dir, os.path.basename(file_path))
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(source_code)

        agent = CompilerAgent(max_iterations=max_attempts)
        try:
            result = agent.heal(source_code, tmp_file)
            return {
                "compiled": bool(result.get("success", False)),
                "attempts": result.get("iterations", 1),
                "time_sec": round(time.perf_counter() - start_time, 3),
                "tier": result.get("tier", "unknown"),
            }
        except Exception as exc:
            return {
                "compiled": False,
                "attempts": 1,
                "time_sec": round(time.perf_counter() - start_time, 3),
                "error": str(exc),
            }


def discover_test_cases(test_dir: str) -> List[str]:
    """Recursively collect all .cpp test case files."""
    test_files = []
    for root, _, files in os.walk(test_dir):
        for f in files:
            if f.endswith(".cpp") and not f.endswith(".heal_backup"):
                test_files.append(os.path.join(root, f))
    test_files.sort()
    return test_files


def run_benchmark(
    test_dir: str = os.path.join(_PROJECT_ROOT, "test_cases"),
    output_csv: str = os.path.join(_PROJECT_ROOT, "results", "baseline.csv"),
    no_llm: bool = False,
    max_attempts: int = 3,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Run full comparative benchmark across test cases."""
    print("=" * 80)
    print("[BENCHMARK] STARTING SELF-HEALING COMPILER COMPARATIVE BENCHMARK")
    print("=" * 80)
    print(f"Test cases directory : {test_dir}")
    print(f"Results CSV output   : {output_csv}")
    print(f"LLM Agent Enabled    : {not no_llm}")
    print(f"Max attempts per test: {max_attempts}")
    print("-" * 80)

    test_files = discover_test_cases(test_dir)
    if limit:
        test_files = test_files[:limit]

    print(f"Discovered {len(test_files)} test case(s) for evaluation.\n")

    classifier = ErrorClassifier()
    if not classifier.is_trained():
        print("Training ErrorClassifier model on dataset...")
        classifier.train_and_save()

    results: List[Dict[str, Any]] = []

    for idx, fpath in enumerate(test_files, start=1):
        try:
            rel_path = os.path.relpath(fpath, _PROJECT_ROOT).replace("\\", "/")
        except ValueError:
            rel_path = os.path.basename(fpath)
        print(f"[{idx:02d}/{len(test_files):02d}] Evaluating {rel_path}...", end=" ", flush=True)

        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                source_code = f.read()
        except Exception as e:
            print(f"❌ Failed to read file: {e}")
            continue

        # 1. Error Category Classification Match
        exp_cat, pred_cat, cat_matched = evaluate_classifier_match(source_code, fpath, classifier)

        # 2. (a) Rule-Based Healer
        rule_res = run_rule_based_healer(source_code, fpath, classifier, max_attempts=max_attempts)

        # 3. (b) LLM Agent (CompilerAgent)
        if no_llm:
            llm_res = {"compiled": "skipped", "attempts": 0, "time_sec": 0.0}
        else:
            llm_res = run_llm_agent(source_code, fpath, max_attempts=max_attempts)

        record = {
            "file": rel_path,
            "expected_category": exp_cat or "none",
            "predicted_category": pred_cat,
            "category_matched": "yes" if cat_matched else "no",
            "rule_compiled": "yes" if rule_res["compiled"] else "no",
            "rule_attempts": rule_res["attempts"],
            "rule_time_sec": rule_res["time_sec"],
            "llm_compiled": (
                "skipped" if llm_res["compiled"] == "skipped"
                else ("yes" if llm_res["compiled"] else "no")
            ),
            "llm_attempts": llm_res["attempts"],
            "llm_time_sec": llm_res["time_sec"],
        }
        results.append(record)

        rule_status = "[HEALED]" if rule_res["compiled"] else "[FAILED]"
        llm_status = "[SKIPPED]" if no_llm else ("[HEALED]" if llm_res["compiled"] else "[FAILED]")
        cat_status = "[MATCH]" if cat_matched else "[MISMATCH]"
        print(f"Rule: {rule_status} | LLM: {llm_status} | Cat: {cat_status}")

    # Write CSV
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    csv_headers = [
        "file",
        "expected_category",
        "predicted_category",
        "category_matched",
        "rule_compiled",
        "rule_attempts",
        "rule_time_sec",
        "llm_compiled",
        "llm_attempts",
        "llm_time_sec",
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(results)

    print("\n" + "=" * 80)
    print(f"[SAVED] Benchmark results successfully saved to: {output_csv}")
    print("=" * 80)

    print_summary_table(results, no_llm=no_llm)
    return results


def print_summary_table(results: List[Dict[str, Any]], no_llm: bool = False) -> None:
    """Print an ASCII summary table of the benchmark metrics."""
    total = len(results)
    if total == 0:
        print("No test cases evaluated.")
        return

    cat_matches = sum(1 for r in results if r["category_matched"] == "yes")
    cat_accuracy = (cat_matches / total) * 100.0

    rule_successes = sum(1 for r in results if r["rule_compiled"] == "yes")
    rule_rate = (rule_successes / total) * 100.0
    rule_avg_attempts = sum(r["rule_attempts"] for r in results) / total
    rule_avg_time = sum(r["rule_time_sec"] for r in results) / total

    print("\nBENCHMARK EVALUATION SUMMARY TABLE")
    print("+" + "-" * 42 + "+" + "-" * 35 + "+")
    print(f"| {'Metric':<40} | {'Result':<33} |")
    print("+" + "-" * 42 + "+" + "-" * 35 + "+")
    print(f"| {'Total Test Fixtures Evaluated':<40} | {total:<33} |")
    print(f"| {'Classifier Category Match Accuracy':<40} | {cat_matches}/{total} ({cat_accuracy:.1f}%) |")
    print(f"| {'Rule-Based Healer Success Rate':<40} | {rule_successes}/{total} ({rule_rate:.1f}%) |")
    print(f"| {'Rule-Based Avg Attempts Used':<40} | {rule_avg_attempts:.2f} attempts{'':<16} |")
    print(f"| {'Rule-Based Avg Wall Time':<40} | {rule_avg_time:.3f} s{'':<21} |")

    if not no_llm:
        llm_successes = sum(1 for r in results if r["llm_compiled"] == "yes")
        llm_rate = (llm_successes / total) * 100.0
        llm_avg_attempts = sum(r["llm_attempts"] for r in results) / total
        llm_avg_time = sum(r["llm_time_sec"] for r in results) / total
        print(f"| {'Gemini Agent (LLM) Success Rate':<40} | {llm_successes}/{total} ({llm_rate:.1f}%) |")
        print(f"| {'Gemini Agent Avg Attempts Used':<40} | {llm_avg_attempts:.2f} attempts{'':<16} |")
        print(f"| {'Gemini Agent Avg Wall Time':<40} | {llm_avg_time:.3f} s{'':<21} |")
    else:
        print(f"| {'Gemini Agent (LLM) Status':<40} | {'SKIPPED (--no-llm)':<33} |")

    print("+" + "-" * 42 + "+" + "-" * 35 + "+\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Green Self-Healing Compiler Benchmark Harness")
    parser.add_argument(
        "--test-dir",
        default=os.path.join(_PROJECT_ROOT, "test_cases"),
        help="Directory containing C++ test case fixtures",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(_PROJECT_ROOT, "results", "baseline.csv"),
        help="Destination path for results CSV file",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM (CompilerAgent) evaluation and run offline",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum healing attempts per test case (default: 3)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of test fixtures to evaluate",
    )
    args = parser.parse_args()

    run_benchmark(
        test_dir=args.test_dir,
        output_csv=args.output,
        no_llm=args.no_llm,
        max_attempts=args.max_attempts,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
