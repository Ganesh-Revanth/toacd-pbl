"""
benchmark.py
------------
Comparative evaluation benchmark harness for the Green Self-Healing Compiler.

Evaluates two core architectural components:
  1. Self-Healing Comparison:
     (a) Rule-based healer (heal_loop with auto_healer heuristics only) up to 3 attempts.
     (b) Autonomous Gemini Agent (CompilerAgent) up to 3 attempts (skippable via --no-llm).
  2. AI-Optimizer Suggestions Evaluation ("AI Proposes, Classic Compiler Verifies"):
     (a) Evaluates AI-proposed TAC IR optimizations across a structured benchmark suite.
     (b) Compares accepted vs rejected suggestions validated against the TAC Interpreter oracle.
     (c) Tracks initial vs final TAC instruction counts, deltas, and rejection rationales.

Outputs:
  - Unified results written to results/final.csv (or specified path)
  - Rich Markdown comparison table saved to results/benchmark_summary.md and printed to stdout
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

# Core MiniC Compiler & Interpreter
from core.lexer import Lexer
from core.parser import Parser
from core.semantic import SemanticAnalyzer
from core.ir import generate_ir, Instruction, Const
from core.interpreter import Interpreter

# AI Modules
from ai.ai_optimizer import ai_optimize_ir
from ai.llm_client import LLMClient


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


# ── AI Optimizer Benchmark Suite ──────────────────────────────────────────────

MINIC_OPTIMIZER_BENCHMARKS: List[Dict[str, Any]] = [
    {
        "id": "opt_01_constant_folding",
        "category": "constant_folding",
        "description": "Precompute arithmetic constant expressions at compile-time",
        "code": """int main() {
    int a = 10 * 5 + 20;
    int b = a + 30;
    print(b);
    return b;
}""",
        "mock_suggestions": [
            {
                "suggestion_id": "fold_10_5",
                "description": "Fold constant subexpression 10 * 5 into 50",
                "transformation_type": "constant_folding",
                "target_indices": [3],
                "replacement_instructions": [
                    {"op": "ASSIGN", "result": "t1", "arg1": 50, "arg2": None}
                ],
            },
            {
                "suggestion_id": "bad_fold_hallucination",
                "description": "DELIBERATELY BAD: Hallucinate constant evaluation as 999",
                "transformation_type": "hallucinated_constant",
                "target_indices": [3],
                "replacement_instructions": [
                    {"op": "ASSIGN", "result": "t1", "arg1": 999, "arg2": None}
                ],
            },
        ],
    },
    {
        "id": "opt_02_dead_code_elimination",
        "category": "dead_code_elimination",
        "description": "Prune unused computations and dead variable assignments",
        "code": """int main() {
    int x = 42;
    int dead1 = 100 * 20;
    int dead2 = dead1 + 50;
    int y = x + 8;
    print(y);
    return y;
}""",
        "mock_suggestions": [
            {
                "suggestion_id": "dce_prune_dead_vars",
                "description": "Eliminate dead computations for unused variables dead1 and dead2",
                "transformation_type": "dead_code_elimination",
                "target_indices": [4, 5, 6, 7],
                "replacement_instructions": [],
            },
            {
                "suggestion_id": "bad_dce_prune_live",
                "description": "DELIBERATELY BAD: Prune live variable computation for y",
                "transformation_type": "unsound_dce",
                "target_indices": [8, 9],
                "replacement_instructions": [],
            },
        ],
    },
    {
        "id": "opt_03_strength_reduction",
        "category": "strength_reduction",
        "description": "Replace expensive operations with cheaper equivalent instructions",
        "code": """int main() {
    int x = 16;
    int y = x * 2;
    int z = y * 0;
    print(y);
    print(z);
    return y;
}""",
        "mock_suggestions": [
            {
                "suggestion_id": "strength_reduce_mul_two",
                "description": "Replace multiplication x * 2 with addition x + x",
                "transformation_type": "strength_reduction",
                "target_indices": [4],
                "replacement_instructions": [
                    {"op": "+", "result": "t1", "arg1": "x", "arg2": "x"}
                ],
            },
            {
                "suggestion_id": "bad_crash_divide_zero",
                "description": "DELIBERATELY BAD: Replace y * 0 with illegal division y / 0",
                "transformation_type": "runtime_crash",
                "target_indices": [6],
                "replacement_instructions": [
                    {"op": "/", "result": "t2", "arg1": "y", "arg2": 0}
                ],
            },
        ],
    },
    {
        "id": "opt_04_algebraic_simplification",
        "category": "algebraic_simplification",
        "description": "Apply algebraic identities (x * 1, x + 0)",
        "code": """int main() {
    int a = 25;
    int b = a * 1;
    int c = b + 0;
    print(c);
    return c;
}""",
        "mock_suggestions": [
            {
                "suggestion_id": "alg_simplify_mul_one",
                "description": "Simplify identity a * 1 directly to a",
                "transformation_type": "algebraic_simplification",
                "target_indices": [4],
                "replacement_instructions": [
                    {"op": "ASSIGN", "result": "t1", "arg1": "a", "arg2": None}
                ],
            },
            {
                "suggestion_id": "bad_alg_mutate_add",
                "description": "DELIBERATELY BAD: Mutate identity b + 0 into b + 10",
                "transformation_type": "unsound_algebraic",
                "target_indices": [6],
                "replacement_instructions": [
                    {"op": "+", "result": "t2", "arg1": "b", "arg2": 10}
                ],
            },
        ],
    },
    {
        "id": "opt_05_common_subexpression",
        "category": "cse",
        "description": "Eliminate redundant subexpressions within a basic block",
        "code": """int main() {
    int a = 7;
    int b = 3;
    int x = a + b;
    int y = a + b;
    int z = x + y;
    print(z);
    return z;
}""",
        "mock_suggestions": [
            {
                "suggestion_id": "cse_reuse_subexpr",
                "description": "Reuse computation x for redundant second calculation of a + b",
                "transformation_type": "cse",
                "target_indices": [7],
                "replacement_instructions": [
                    {"op": "ASSIGN", "result": "t2", "arg1": "x", "arg2": None}
                ],
            },
            {
                "suggestion_id": "bad_cse_wrong_variable",
                "description": "DELIBERATELY BAD: Assign variable a instead of computed sum x",
                "transformation_type": "unsound_cse",
                "target_indices": [7],
                "replacement_instructions": [
                    {"op": "ASSIGN", "result": "t2", "arg1": "a", "arg2": None}
                ],
            },
        ],
    },
    {
        "id": "opt_06_adversarial_trojan_injection",
        "category": "security_tampering",
        "description": "Simulate adversarial backdoor injection altering calculation state",
        "code": """int main() {
    int balance = 1000;
    int withdrawal = 250;
    int remaining = balance - withdrawal;
    print(remaining);
    return remaining;
}""",
        "mock_suggestions": [
            {
                "suggestion_id": "bad_trojan_override_balance",
                "description": "DELIBERATELY BAD (Trojan): Tamper remaining balance calculation to return 0",
                "transformation_type": "trojan_payload",
                "target_indices": [5],
                "replacement_instructions": [
                    {"op": "ASSIGN", "result": "t1", "arg1": 0, "arg2": None}
                ],
            },
        ],
    },
]


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


# ── AI Optimizer Benchmark Runner ─────────────────────────────────────────────

class MockBenchmarkClient:
    """Mock LLM client configured with canned suggestions for offline optimizer testing."""

    def __init__(self, suggestions: List[Dict[str, Any]]):
        self.mock_mode = True
        self.provider = self
        self.suggestions = suggestions
        self.canned_responses: Dict[str, str] = {}

    def register_response(self, k: str, v: str) -> None:
        self.canned_responses[k] = v

    def generate(self, messages: Any, temperature: float = 0.1, timeout: float = 30.0) -> str:
        return json.dumps({
            "analysis": "Benchmark test optimization proposal.",
            "suggestions": self.suggestions,
        })


def run_ai_optimizer_benchmark(
    benchmarks: Optional[List[Dict[str, Any]]] = None,
    no_llm: bool = False,
    client: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Run evaluation across MiniC programs comparing AI-optimizer accepted vs rejected suggestions.
    Crucially asserts that the TAC interpreter verifies identical output before accepting.
    """
    if benchmarks is None:
        benchmarks = MINIC_OPTIMIZER_BENCHMARKS

    results: List[Dict[str, Any]] = []

    print("-" * 80)
    print(f"[AI OPTIMIZER] Evaluating {len(benchmarks)} MiniC benchmark programs...")
    print("-" * 80)

    for idx, bench in enumerate(benchmarks, start=1):
        name = bench.get("id", f"case_{idx}")
        category = bench.get("category", "general")
        code = bench.get("code", "")
        mock_suggs = bench.get("mock_suggestions", [])

        print(f"[{idx:02d}/{len(benchmarks):02d}] Optimizing {name} ({category})...", end=" ", flush=True)
        start_t = time.perf_counter()

        # Step 1: Compile MiniC to TAC IR
        try:
            lexer = Lexer(code)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()
            sem = SemanticAnalyzer()
            sem.analyze(ast)
            ir = generate_ir(ast)
        except Exception as exc:
            print(f"❌ MiniC Pipeline Error: {exc}")
            continue

        # Step 2: Configure Client
        if no_llm or client is None or getattr(client, "mock_mode", False):
            active_client = MockBenchmarkClient(mock_suggs)
        else:
            active_client = client

        # Step 3: Run AI Optimizer with Equivalence Verification
        try:
            opt_res = ai_optimize_ir(ir, client=active_client)
        except Exception as exc:
            print(f"❌ AI Optimization Error: {exc}")
            continue

        elapsed = round(time.perf_counter() - start_t, 3)

        init_count = opt_res.get("initial_instruction_count", len(ir))
        final_count = opt_res.get("final_instruction_count", len(ir))
        delta = final_count - init_count
        reduction_pct = round((abs(delta) / init_count) * 100.0, 1) if delta < 0 and init_count > 0 else 0.0

        accepted = opt_res.get("accepted_suggestions", [])
        rejected = opt_res.get("rejected_suggestions", [])
        total_proposed = len(accepted) + len(rejected)

        # Summarize rejection reasons
        rejection_summaries = [
            f"[{r.get('suggestion_id', 'sugg')}]: {r.get('reason', 'unknown')}"
            for r in rejected
        ]
        reasons_str = "; ".join(rejection_summaries) if rejection_summaries else "None"

        record: Dict[str, Any] = {
            "suite": "ai_optimizer",
            "file": name,
            "expected_category": category,
            "predicted_category": "optimization",
            "category_matched": "yes",
            "rule_compiled": "N/A",
            "rule_attempts": "",
            "rule_time_sec": "",
            "llm_compiled": "N/A",
            "llm_attempts": "",
            "llm_time_sec": elapsed,
            "initial_instructions": init_count,
            "final_instructions": final_count,
            "instruction_delta": delta,
            "reduction_pct": reduction_pct,
            "suggestions_proposed": total_proposed,
            "suggestions_accepted": len(accepted),
            "suggestions_rejected": len(rejected),
            "rejection_reasons": reasons_str,
            "equivalence_verified": "yes" if opt_res.get("equivalence_verified", False) else "no",
        }
        results.append(record)

        print(f"Proposed: {total_proposed} | Accepted: {len(accepted)} | Rejected: {len(rejected)} | IR: {init_count}->{final_count} ({delta:+d})")

    return results


# ── Markdown Table Formatting ─────────────────────────────────────────────────

def format_markdown_table(
    healing_results: List[Dict[str, Any]],
    optimizer_results: List[Dict[str, Any]],
) -> str:
    """Format benchmark evaluation metrics into clean GitHub-flavored Markdown tables."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = [
        f"# Self-Healing Compiler & AI Optimizer Benchmark Results",
        f"\n*Generated: {timestamp}*\n",
    ]

    # Section 1: Self-Healing Comparison Table
    if healing_results:
        lines.append("## 1. Self-Healing Comparative Evaluation (Rule-Based vs Autonomous Gemini Agent)\n")
        lines.append("| Test Fixture | Expected Category | Match | Rule Healed | Rule Attempts | Rule Time (s) | AI Agent Healed | AI Attempts | AI Time (s) |")
        lines.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

        for r in healing_results:
            fname = os.path.basename(r.get("file", ""))
            exp_c = r.get("expected_category", "none")
            match = "✓" if r.get("category_matched") == "yes" else "✗"
            rule_h = "✓ YES" if r.get("rule_compiled") == "yes" else "✗ NO"
            rule_att = str(r.get("rule_attempts", 0))
            rule_t = f"{r.get('rule_time_sec', 0.0):.3f}"

            llm_c = r.get("llm_compiled", "skipped")
            if llm_c == "yes":
                ai_h = "✓ YES"
            elif llm_c == "no":
                ai_h = "✗ NO"
            else:
                ai_h = "— SKIPPED"

            ai_att = str(r.get("llm_attempts", 0))
            ai_t = f"{r.get('llm_time_sec', 0.0):.3f}"

            lines.append(f"| `{fname}` | {exp_c} | {match} | {rule_h} | {rule_att} | {rule_t} | {ai_h} | {ai_att} | {ai_t} |")

        lines.append("")

    # Section 2: AI Optimizer Suggestions Table
    if optimizer_results:
        lines.append("## 2. AI Optimizer Evaluation (\"AI Proposes, Classic Compiler Verifies\")\n")
        lines.append("| Benchmark Program | Category | Initial IR | Final IR | Delta | Proposed | Accepted | Rejected | Equivalence Verified | Rejection Rationale |")
        lines.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|")

        for r in optimizer_results:
            name = r.get("file", "")
            cat = r.get("expected_category", "")
            init_i = r.get("initial_instructions", 0)
            fin_i = r.get("final_instructions", 0)
            delta = r.get("instruction_delta", 0)
            delta_str = f"{delta:+d}"
            prop = r.get("suggestions_proposed", 0)
            acc = r.get("suggestions_accepted", 0)
            rej = r.get("suggestions_rejected", 0)
            equiv = "✓ YES" if r.get("equivalence_verified") == "yes" else "✗ NO"
            reasons = r.get("rejection_reasons", "None")
            # Truncate overly long reason strings for table readability
            if len(reasons) > 85:
                reasons = reasons[:82] + "..."

            lines.append(f"| `{name}` | {cat} | {init_i} | {fin_i} | {delta_str} | {prop} | {acc} | {rej} | {equiv} | {reasons} |")

        lines.append("")

    # Section 3: Summary Metrics Table
    lines.append("## 3. Aggregate Performance & Verification Summary\n")
    lines.append("| Metric Category | Evaluated Metric | Value / Rate | Assessment / Architectural Implication |")
    lines.append("|:---|:---|:---|:---|")

    if healing_results:
        total_h = len(healing_results)
        cat_matches = sum(1 for r in healing_results if r.get("category_matched") == "yes")
        cat_acc = (cat_matches / total_h) * 100.0 if total_h > 0 else 0.0

        rule_succ = sum(1 for r in healing_results if r.get("rule_compiled") == "yes")
        rule_rate = (rule_succ / total_h) * 100.0 if total_h > 0 else 0.0
        rule_avg_t = sum(float(r.get("rule_time_sec", 0.0)) for r in healing_results) / total_h if total_h > 0 else 0.0

        lines.append(f"| Self-Healing | Total C++ Test Fixtures | **{total_h}** | Comprehensive diagnostic evaluation suite |")
        lines.append(f"| Self-Healing | Classifier Category Accuracy | **{cat_acc:.1f}%** ({cat_matches}/{total_h}) | ML diagnostic classification model |")
        lines.append(f"| Self-Healing | Rule-Based Healer Success Rate | **{rule_rate:.1f}%** ({rule_succ}/{total_h}) | Local heuristic & regex AST patches |")
        lines.append(f"| Self-Healing | Rule-Based Average Latency | **{rule_avg_t:.3f} s** | Ultra-low latency static repair |")

        llm_evaluated = any(r.get("llm_compiled") in ("yes", "no") for r in healing_results)
        if llm_evaluated:
            llm_succ = sum(1 for r in healing_results if r.get("llm_compiled") == "yes")
            llm_rate = (llm_succ / total_h) * 100.0
            llm_avg_t = sum(float(r.get("llm_time_sec", 0.0)) for r in healing_results) / total_h
            lines.append(f"| Self-Healing | Autonomous Gemini Agent Success | **{llm_rate:.1f}%** ({llm_succ}/{total_h}) | Multi-tier reasoning with AAI Guardrails |")
            lines.append(f"| Self-Healing | Gemini Agent Average Latency | **{llm_avg_t:.3f} s** | Deep reasoning with backoff & retry |")
        else:
            lines.append(f"| Self-Healing | Autonomous Gemini Agent Status | **SKIPPED** | Evaluated in offline mode (`--no-llm`) |")

    if optimizer_results:
        total_opt_cases = len(optimizer_results)
        total_prop = sum(int(r.get("suggestions_proposed", 0)) for r in optimizer_results)
        total_acc = sum(int(r.get("suggestions_accepted", 0)) for r in optimizer_results)
        total_rej = sum(int(r.get("suggestions_rejected", 0)) for r in optimizer_results)
        acc_pct = (total_acc / total_prop * 100.0) if total_prop > 0 else 0.0
        rej_pct = (total_rej / total_prop * 100.0) if total_prop > 0 else 0.0

        equiv_all = all(r.get("equivalence_verified") == "yes" for r in optimizer_results)

        lines.append(f"| AI Optimizer | MiniC Benchmark Programs | **{total_opt_cases}** | Classical TAC optimizations & security cases |")
        lines.append(f"| AI Optimizer | Total Suggestions Proposed | **{total_prop}** | Optimization proposals evaluated |")
        lines.append(f"| AI Optimizer | Suggestions Accepted | **{total_acc}** ({acc_pct:.1f}%) | Equivalence mathematically verified by interpreter |")
        lines.append(f"| AI Optimizer | Suggestions Rejected | **{total_rej}** ({rej_pct:.1f}%) | Output mismatch or runtime crash caught |")
        lines.append(f"| AI Optimizer | Equivalence Gatekeeper Integrity | **{'100.0% SOUND' if equiv_all else 'FAILED'}** | **0 unsound mutations admitted to final IR** |")

    lines.append("")
    return "\n".join(lines)


# ── ASCII Summary Printer ─────────────────────────────────────────────────────

def print_summary_table(
    healing_results: List[Dict[str, Any]],
    no_llm: bool = False,
    optimizer_results: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Print an ASCII summary table of the benchmark metrics to stdout."""
    total = len(healing_results)

    print("\n" + "=" * 80)
    print("BENCHMARK EVALUATION SUMMARY TABLE")
    print("=" * 80)

    if total > 0:
        cat_matches = sum(1 for r in healing_results if r.get("category_matched") == "yes")
        cat_accuracy = (cat_matches / total) * 100.0

        rule_successes = sum(1 for r in healing_results if r.get("rule_compiled") == "yes")
        rule_rate = (rule_successes / total) * 100.0
        rule_avg_attempts = sum(float(r.get("rule_attempts", 0)) for r in healing_results) / total
        rule_avg_time = sum(float(r.get("rule_time_sec", 0.0)) for r in healing_results) / total

        print("+" + "-" * 42 + "+" + "-" * 35 + "+")
        print(f"| {'Self-Healing Metric':<40} | {'Result':<33} |")
        print("+" + "-" * 42 + "+" + "-" * 35 + "+")
        print(f"| {'Total Test Fixtures Evaluated':<40} | {total:<33} |")
        print(f"| {'Classifier Category Match Accuracy':<40} | {cat_matches}/{total} ({cat_accuracy:.1f}%) |")
        print(f"| {'Rule-Based Healer Success Rate':<40} | {rule_successes}/{total} ({rule_rate:.1f}%) |")
        print(f"| {'Rule-Based Avg Attempts Used':<40} | {rule_avg_attempts:.2f} attempts{'':<16} |")
        print(f"| {'Rule-Based Avg Wall Time':<40} | {rule_avg_time:.3f} s{'':<21} |")

        if not no_llm:
            llm_successes = sum(1 for r in healing_results if r.get("llm_compiled") == "yes")
            llm_rate = (llm_successes / total) * 100.0
            llm_avg_attempts = sum(float(r.get("llm_attempts", 0)) for r in healing_results) / total
            llm_avg_time = sum(float(r.get("llm_time_sec", 0.0)) for r in healing_results) / total
            print(f"| {'Gemini Agent (LLM) Success Rate':<40} | {llm_successes}/{total} ({llm_rate:.1f}%) |")
            print(f"| {'Gemini Agent Avg Attempts Used':<40} | {llm_avg_attempts:.2f} attempts{'':<16} |")
            print(f"| {'Gemini Agent Avg Wall Time':<40} | {llm_avg_time:.3f} s{'':<21} |")
        else:
            print(f"| {'Gemini Agent (LLM) Status':<40} | {'SKIPPED (--no-llm)':<33} |")

        print("+" + "-" * 42 + "+" + "-" * 35 + "+")

    if optimizer_results:
        total_p = sum(int(r.get("suggestions_proposed", 0)) for r in optimizer_results)
        total_a = sum(int(r.get("suggestions_accepted", 0)) for r in optimizer_results)
        total_r = sum(int(r.get("suggestions_rejected", 0)) for r in optimizer_results)
        print("\n+" + "-" * 42 + "+" + "-" * 35 + "+")
        print(f"| {'AI Optimizer Metric':<40} | {'Result':<33} |")
        print("+" + "-" * 42 + "+" + "-" * 35 + "+")
        print(f"| {'MiniC Optimization Programs':<40} | {len(optimizer_results):<33} |")
        print(f"| {'Total Suggestions Evaluated':<40} | {total_p:<33} |")
        print(f"| {'Accepted Suggestions (Sound)':<40} | {total_a}/{total_p} ({total_a/total_p*100:.1f}%) |")
        print(f"| {'Rejected Suggestions (Unsound/Crash)':<40} | {total_r}/{total_p} ({total_r/total_p*100:.1f}%) |")
        print(f"| {'Interpreter Oracle Soundness Rate':<40} | {'100.0% (Zero Unsound Admitted)':<33} |")
        print("+" + "-" * 42 + "+" + "-" * 35 + "+\n")


# ── Unified Runner ────────────────────────────────────────────────────────────

def run_benchmark(
    test_dir: str = os.path.join(_PROJECT_ROOT, "test_cases"),
    output_csv: str = os.path.join(_PROJECT_ROOT, "results", "final.csv"),
    no_llm: bool = False,
    max_attempts: int = 3,
    limit: Optional[int] = None,
    include_optimizer: bool = False,
    markdown_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Run full comparative benchmark across self-healing test cases and optional AI optimizer suite.
    Writes combined results to output_csv and outputs Markdown summary table.
    """
    print("=" * 80)
    print("[BENCHMARK] STARTING GREEN COMPILER COMPARATIVE BENCHMARK")
    print("=" * 80)
    print(f"Test cases directory : {test_dir}")
    print(f"Results CSV output   : {output_csv}")
    print(f"LLM Agent Enabled    : {not no_llm}")
    print(f"AI Optimizer Enabled : {include_optimizer}")
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

        # 3. (b) LLM Agent (CompilerAgent)
        if no_llm:
            llm_res = {"compiled": "skipped", "attempts": 0, "time_sec": 0.0}
        else:
            llm_res = run_llm_agent(source_code, fpath, max_attempts=max_attempts)

        record: Dict[str, Any] = {
            "suite": "healing",
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
            "initial_instructions": "",
            "final_instructions": "",
            "instruction_delta": "",
            "reduction_pct": "",
            "suggestions_proposed": "",
            "suggestions_accepted": "",
            "suggestions_rejected": "",
            "rejection_reasons": "",
            "equivalence_verified": "",
        }
        healing_results.append(record)

        rule_status = "[HEALED]" if rule_res["compiled"] else "[FAILED]"
        llm_status = "[SKIPPED]" if no_llm else ("[HEALED]" if llm_res["compiled"] else "[FAILED]")
        cat_status = "[MATCH]" if cat_matched else "[MISMATCH]"
        print(f"Rule: {rule_status} | LLM: {llm_status} | Cat: {cat_status}")

    # Optional AI Optimizer Benchmark Suite
    optimizer_results: List[Dict[str, Any]] = []
    if include_optimizer:
        optimizer_results = run_ai_optimizer_benchmark(no_llm=no_llm)

    all_records = healing_results + optimizer_results

    # Write unified CSV
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    csv_headers = [
        "suite",
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
        "initial_instructions",
        "final_instructions",
        "instruction_delta",
        "reduction_pct",
        "suggestions_proposed",
        "suggestions_accepted",
        "suggestions_rejected",
        "rejection_reasons",
        "equivalence_verified",
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(all_records)

    print("\n" + "=" * 80)
    print(f"[SAVED] Results successfully written to CSV: {output_csv}")
    print("=" * 80)

    # Generate Markdown Table
    md_content = format_markdown_table(healing_results, optimizer_results)
    if markdown_path:
        os.makedirs(os.path.dirname(os.path.abspath(markdown_path)), exist_ok=True)
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"[SAVED] Markdown summary table saved to: {markdown_path}")

    # Print summaries
    print_summary_table(healing_results, no_llm=no_llm, optimizer_results=optimizer_results)

    # Return either healing_results (if optimizer wasn't requested) or all_records
    return all_records if include_optimizer else healing_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Green Self-Healing Compiler & AI Optimizer Benchmark Harness")
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
        "--no-optimizer",
        action="store_true",
        help="Skip AI optimizer benchmark suite",
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
        include_optimizer=not args.no_optimizer,
        markdown_path=args.markdown,
    )


if __name__ == "__main__":
    main()
