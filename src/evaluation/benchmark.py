"""
benchmark.py
------------
Comparative evaluation benchmark harness for the Green Self-Healing Compiler.

Evaluates:
  1. Self-Healing Comparative Evaluation:
     - Rule-Based Heuristic Patcher (heal_loop + auto_healer) up to max_attempts.
     - Autonomous Gemini Agent (CompilerAgent) up to max_attempts.
     - Methodological Integrity: Distinguishes baseline clean files from broken files requiring repair;
       computes the true healing success rate strictly over broken files.

Outputs:
  - Formatted results written to results/final.csv
  - Markdown summary table saved to results/benchmark_summary.md and printed to stdout
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import time
import warnings
from datetime import datetime
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

from ai.llm_client import LLMClient, load_env_file, DEFAULT_MODEL

# Auto-load .env credentials if present
load_env_file()


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
                "healed": False,
                "was_clean": True,
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
                    "healed": True,
                    "was_clean": False,
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
                    "healed": True,
                    "was_clean": False,
                }

        return {
            "compiled": False,
            "attempts": attempts_used,
            "time_sec": round(time.perf_counter() - start_time, 3),
            "healed": False,
            "was_clean": False,
        }


def run_llm_agent(
    source_code: str,
    file_path: str,
    max_attempts: int = 3,
    client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    """Run autonomous Gemini compiler agent up to max_attempts."""
    start_time = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = os.path.join(tmp_dir, os.path.basename(file_path))
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(source_code)

        agent = CompilerAgent(max_iterations=max_attempts, client=client)
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
    """Recursively collect all .cpp test case files, excluding backups and duplicates."""
    test_files = []
    for root, _, files in os.walk(test_dir):
        for f in files:
            if f.endswith(".cpp") and not f.endswith(".heal_backup") and "- Copy" not in f:
                test_files.append(os.path.join(root, f))
    test_files.sort()
    return test_files


# ── Markdown Table Formatting ─────────────────────────────────────────────────

def format_markdown_table(
    healing_results: List[Dict[str, Any]],
) -> str:
    """Format benchmark evaluation metrics into clean, technically accurate GitHub-flavored Markdown."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = [
        f"# Self-Healing Compiler Benchmark Results",
        f"\n*Generated: {timestamp}*",
        f"*Default Model: `{DEFAULT_MODEL}` | Execution: Isolated Toolchain Sandbox*\n",
    ]

    # Section 1: Self-Healing Comparison Table
    if healing_results:
        lines.append("## 1. Self-Healing Comparative Evaluation (Rule-Based vs Autonomous Gemini Agent)\n")
        lines.append("> **Methodology Note:** Fixtures are separated into baseline clean files (which require 0 repair attempts) and broken files requiring repair. Success rates are computed strictly over files needing repair.\n")
        lines.append("| Test Fixture | Expected Category | Match | Baseline Clean? | Rule Healed | Rule Attempts | Rule Time (s) | AI Agent Healed | AI Attempts | AI Time (s) |")
        lines.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

        for r in healing_results:
            fname = os.path.basename(r.get("file", ""))
            exp_c = r.get("expected_category", "none")
            match = "✓" if r.get("category_matched") == "yes" else "✗"
            was_clean = "✓ YES" if r.get("baseline_clean") else "NO (Broken)"

            if r.get("baseline_clean"):
                rule_h = "— CLEAN"
                rule_att = "0"
            else:
                rule_h = "✓ YES" if r.get("rule_compiled") == "yes" else "✗ NO"
                rule_att = str(r.get("rule_attempts", 0))

            rule_t = f"{float(r.get('rule_time_sec', 0.0)):.3f}"

            llm_c = r.get("llm_compiled", "skipped")
            if r.get("baseline_clean"):
                ai_h = "— CLEAN"
                ai_att = "0"
            elif llm_c == "yes":
                ai_h = "✓ YES"
                ai_att = str(r.get("llm_attempts", 0))
            elif llm_c == "no":
                ai_h = "✗ NO"
                ai_att = str(r.get("llm_attempts", 0))
            else:
                ai_h = "— SKIPPED"
                ai_att = "0"

            ai_t = f"{float(r.get('llm_time_sec', 0.0)):.3f}"

            lines.append(f"| `{fname}` | {exp_c} | {match} | {was_clean} | {rule_h} | {rule_att} | {rule_t} | {ai_h} | {ai_att} | {ai_t} |")

        lines.append("")

    # Section 2: Aggregate Summary
    lines.append("## 2. Aggregate Performance & Verification Summary\n")
    lines.append("| Metric Category | Evaluated Metric | Value / Rate | Technical Assessment & Boundary |")
    lines.append("|:---|:---|:---|:---|")

    if healing_results:
        total_h = len(healing_results)
        clean_count = sum(1 for r in healing_results if r.get("baseline_clean"))
        broken_count = total_h - clean_count

        cat_matches = sum(1 for r in healing_results if r.get("category_matched") == "yes")
        cat_acc = (cat_matches / total_h) * 100.0 if total_h > 0 else 0.0

        rule_healed = sum(1 for r in healing_results if not r.get("baseline_clean") and r.get("rule_compiled") == "yes")
        rule_rate = (rule_healed / broken_count * 100.0) if broken_count > 0 else 0.0
        rule_avg_t = sum(float(r.get("rule_time_sec", 0.0)) for r in healing_results) / total_h if total_h > 0 else 0.0

        lines.append(f"| Self-Healing | Total C++ Test Fixtures | **{total_h}** | Evaluated fixtures in `test_cases/` |")
        lines.append(f"| Self-Healing | Baseline Clean Files | **{clean_count}/{total_h}** ({clean_count/total_h*100:.1f}%) | Compiled with 0 errors initially (excluded from heal rate) |")
        lines.append(f"| Self-Healing | Broken Files Requiring Repair | **{broken_count}/{total_h}** ({broken_count/total_h*100:.1f}%) | Ground-truth compilation failures requiring repair |")
        lines.append(f"| Self-Healing | Classifier Category Accuracy | **{cat_acc:.1f}%** ({cat_matches}/{total_h}) | Evaluated against heuristic metadata labels |")
        lines.append(f"| Self-Healing | **Rule-Based Repair Success Rate** | **{rule_rate:.1f}%** ({rule_healed}/{broken_count}) | Simple localized regex AST fixes on broken files |")
        lines.append(f"| Self-Healing | Rule-Based Average Latency | **{rule_avg_t:.3f} s** | Ultra-low latency static repair pass |")

        llm_evaluated = any(not r.get("baseline_clean") and r.get("llm_compiled") in ("yes", "no") for r in healing_results)
        if llm_evaluated:
            llm_healed = sum(1 for r in healing_results if not r.get("baseline_clean") and r.get("llm_compiled") == "yes")
            llm_rate = (llm_healed / broken_count * 100.0) if broken_count > 0 else 0.0
            llm_avg_t = sum(float(r.get("llm_time_sec", 0.0)) for r in healing_results if not r.get("baseline_clean")) / broken_count if broken_count > 0 else 0.0
            lines.append(f"| Self-Healing | **Autonomous Gemini Agent Success** | **{llm_rate:.1f}%** ({llm_healed}/{broken_count}) | Multi-tier reasoning with backoff & AAI Guardrails |")
            lines.append(f"| Self-Healing | Gemini Agent Average Latency | **{llm_avg_t:.3f} s** | Deep contextual analysis on broken files |")
            lines.append(f"| Self-Healing | **AI Healing Advantage (Lift)** | **+{llm_rate - rule_rate:.1f}%** | Improvement over static rule-based heuristics |")
        else:
            lines.append(f"| Self-Healing | Autonomous Gemini Agent Status | **SKIPPED** | Offline evaluation (`--no-llm`) |")

    lines.append("")
    return "\n".join(lines)


# ── ASCII Summary Printer ─────────────────────────────────────────────────────

def print_summary_table(
    healing_results: List[Dict[str, Any]],
    no_llm: bool = False,
) -> None:
    """Print an ASCII summary table of the benchmark metrics to stdout."""
    total = len(healing_results)

    print("\n" + "=" * 80)
    print("BENCHMARK EVALUATION SUMMARY TABLE")
    print("=" * 80)

    if total > 0:
        clean_count = sum(1 for r in healing_results if r.get("baseline_clean"))
        broken_count = total - clean_count

        cat_matches = sum(1 for r in healing_results if r.get("category_matched") == "yes")
        cat_accuracy = (cat_matches / total) * 100.0

        rule_healed = sum(1 for r in healing_results if not r.get("baseline_clean") and r.get("rule_compiled") == "yes")
        rule_rate = (rule_healed / broken_count * 100.0) if broken_count > 0 else 0.0

        print("+" + "-" * 42 + "+" + "-" * 35 + "+")
        print(f"| {'Self-Healing Metric':<40} | {'Result':<33} |")
        print("+" + "-" * 42 + "+" + "-" * 35 + "+")
        print(f"| {'Total Test Fixtures Evaluated':<40} | {total:<33} |")
        print(f"| {'Baseline Clean (No repair needed)':<40} | {clean_count}/{total} ({clean_count/total*100:.1f}%) |")
        print(f"| {'Broken Fixtures Requiring Repair':<40} | {broken_count}/{total} ({broken_count/total*100:.1f}%) |")
        print(f"| {'Classifier Category Match Accuracy':<40} | {cat_matches}/{total} ({cat_accuracy:.1f}%) |")
        print(f"| {'Rule-Based Repair Success Rate':<40} | {rule_healed}/{broken_count} ({rule_rate:.1f}%) |")

        if not no_llm:
            llm_healed = sum(1 for r in healing_results if not r.get("baseline_clean") and r.get("llm_compiled") == "yes")
            llm_rate = (llm_healed / broken_count * 100.0) if broken_count > 0 else 0.0
            print(f"| {'Gemini Agent Repair Success Rate':<40} | {llm_healed}/{broken_count} ({llm_rate:.1f}%) |")
            print(f"| {'AI Agent Healing Advantage (Lift)':<40} | +{llm_rate - rule_rate:.1f}% |")
        else:
            print(f"| {'Gemini Agent (LLM) Status':<40} | {'SKIPPED (--no-llm)':<33} |")

        print("+" + "-" * 42 + "+" + "-" * 35 + "+\n")


# ── Unified Runner ────────────────────────────────────────────────────────────

def run_benchmark(
    test_dir: str = os.path.join(_PROJECT_ROOT, "test_cases"),
    output_csv: str = os.path.join(_PROJECT_ROOT, "results", "final.csv"),
    no_llm: bool = False,
    max_attempts: int = 3,
    limit: Optional[int] = None,
    markdown_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Run full comparative benchmark across self-healing test cases.
    Writes results to output_csv and outputs Markdown summary table.
    """
    print("=" * 80)
    print("[BENCHMARK] STARTING GREEN COMPILER COMPARATIVE BENCHMARK")
    print("=" * 80)
    print(f"Test cases directory     : {test_dir}")
    print(f"Results CSV output       : {output_csv}")
    print(f"LLM Agent Enabled        : {not no_llm}")
    print(f"Max attempts per test    : {max_attempts}")
    print("-" * 80)

    test_files = discover_test_cases(test_dir)
    if limit:
        test_files = test_files[:limit]

    print(f"Discovered {len(test_files)} test case(s) for evaluation.\n")

    classifier = ErrorClassifier()
    if not classifier.is_trained():
        print("Training ErrorClassifier model on dataset...")
        classifier.train_and_save()

    healing_results: List[Dict[str, Any]] = []

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
        was_clean = rule_res.get("was_clean", False)

        # 3. (b) LLM Agent (CompilerAgent)
        if no_llm:
            llm_res = {"compiled": "skipped", "attempts": 0, "time_sec": 0.0}
        elif was_clean:
            # Clean files do not require LLM healing
            llm_res = {"compiled": True, "attempts": 0, "time_sec": 0.0, "tier": "clean"}
        else:
            llm_res = run_llm_agent(source_code, fpath, max_attempts=max_attempts)
            time.sleep(0.8)

        record: Dict[str, Any] = {
            "suite": "healing",
            "file": rel_path,
            "expected_category": exp_cat or "none",
            "predicted_category": pred_cat,
            "category_matched": "yes" if cat_matched else "no",
            "baseline_clean": was_clean,
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
        healing_results.append(record)

        if was_clean:
            rule_status = "[CLEAN]"
            llm_status = "[CLEAN]"
        else:
            rule_status = "[HEALED]" if rule_res["compiled"] else "[FAILED]"
            llm_status = "[SKIPPED]" if no_llm else ("[HEALED]" if llm_res["compiled"] else "[FAILED]")

        cat_status = "[MATCH]" if cat_matched else "[MISMATCH]"
        print(f"Rule: {rule_status} | LLM: {llm_status} | Cat: {cat_status}")

    # Write unified CSV
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    csv_headers = [
        "suite",
        "file",
        "expected_category",
        "predicted_category",
        "category_matched",
        "baseline_clean",
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
        writer.writerows(healing_results)

    print("\n" + "=" * 80)
    print(f"[SAVED] Results successfully written to CSV: {output_csv}")
    print("=" * 80)

    # Generate Markdown Table
    md_content = format_markdown_table(
        healing_results=healing_results,
    )
    if markdown_path:
        os.makedirs(os.path.dirname(os.path.abspath(markdown_path)), exist_ok=True)
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"[SAVED] Markdown summary table saved to: {markdown_path}")

    # Print summaries
    print_summary_table(
        healing_results,
        no_llm=no_llm,
    )

    return healing_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Green Self-Healing Compiler Benchmark Harness")
    parser.add_argument(
        "--test-dir",
        default=os.path.join(_PROJECT_ROOT, "test_cases"),
        help="Directory containing C++ test case fixtures",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(_PROJECT_ROOT, "results", "final.csv"),
        help="Destination path for results CSV file",
    )
    parser.add_argument(
        "--markdown",
        default=os.path.join(_PROJECT_ROOT, "results", "benchmark_summary.md"),
        help="Destination path for Markdown summary table",
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
        markdown_path=args.markdown,
    )


if __name__ == "__main__":
    main()
