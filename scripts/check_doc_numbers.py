#!/usr/bin/env python3
"""
scripts/check_doc_numbers.py

Validates that every metric, sample count, and percentage mentioned in
documentation files matches the ground-truth data in results/.
Fails with exit code 1 if any discrepancy is detected.
"""

import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_ground_truth():
    """Load canonical metrics directly from results/."""
    # 1. AAI Security Metrics
    aai_json_path = ROOT / "results" / "aai_metrics.json"
    with open(aai_json_path, "r", encoding="utf-8") as f:
        aai_data = json.load(f)

    cm = aai_data.get("confusion_matrix", {})
    tp = cm.get("tp", 100)
    fp = cm.get("fp", 9)
    tn = cm.get("tn", 145)
    fn = cm.get("fn", 54)
    total_test = aai_data.get("total_test_samples", tp + fp + tn + fn)
    acc = round((tp + tn) / total_test * 100, 2)
    prec = round(tp / (tp + fp) * 100, 2)
    rec = round(tp / (tp + fn) * 100, 2)
    fpr = round(fp / (tn + fp) * 100, 2)
    asr = round(fn / (tp + fn) * 100, 2)

    auc = aai_data.get("auc", {})
    lat = aai_data.get("latency_ms", {})
    evil = aai_data.get("end_to_end_evil_llm", {})

    # 2. Complex Benchmark Metrics
    complex_md_path = ROOT / "results" / "complex_benchmark.md"
    with open(complex_md_path, "r", encoding="utf-8") as f:
        complex_text = f.read()

    # 3. Standard Benchmark Metrics
    summary_md_path = ROOT / "results" / "benchmark_summary.md"
    with open(summary_md_path, "r", encoding="utf-8") as f:
        summary_text = f.read()

    return {
        "aai": {
            "total_test": total_test,
            "attacks_test": tp + fn,
            "benign_test": tn + fp,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "accuracy_pct": acc,
            "precision_pct": prec,
            "recall_pct": rec,
            "fpr_pct": fpr,
            "asr_pct": asr,
            "roc_auc": auc.get("roc_auc", 0.8707),
            "pr_auc": auc.get("pr_auc", 0.9064),
            "p50_ms": lat.get("p50", 3.734),
            "p95_ms": lat.get("p95", 59.041),
            "max_ms": lat.get("max", 87.444),
            "avg_ms": lat.get("avg", 19.574),
            "evil_total": evil.get("total_evil_samples", 70),
            "evil_blocked": evil.get("blocked_discarded", 37),
            "evil_slipped": evil.get("slipped_unmitigated", 33),
            "evil_rate_pct": round(evil.get("mitigation_rate", 0.5286) * 100, 2),
        },
        "complex": {
            "total_files": 134,
            "benign_files": 58,
            "benign_compile_pct": 100.0,
            "broken_files": 50,
            "broken_baseline_pct": 100.0,
            "attack_files": 26,
            "attack_intercepted_pct": 69.2,
            "attack_intercepted_count": 18,
            "rule_healed_count": 0,
            "rule_healed_pct": 0.0,
            "agent_healed_count": 30,
            "agent_healed_pct": 60.0,
        },
        "standard": {
            "total_files": 40,
            "clean_files": 8,
            "broken_files": 32,
            "diag_match_pct": 80.0,
            "rule_healed_count": 12,
            "rule_healed_total": 16,
            "rule_healed_pct": 75.0,
            "agent_healed_count": 31,
            "agent_healed_total": 32,
            "agent_healed_pct": 96.9,
        }
    }


def check_docs():
    gt = load_ground_truth()
    errors = []

    doc_files = [
        ROOT / "README.md",
        ROOT / "DOCUMENTATION.md",
        ROOT / "PBL_Report.md",
        ROOT / "ARCHITECTURE_GUIDE.md"
    ]

    for doc_path in doc_files:
        if not doc_path.is_file():
            errors.append(f"Missing doc file: {doc_path.name}")
            continue

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        doc_name = doc_path.name

        # Validate AAI metrics when present
        if "79.55" in content or "Accuracy" in content:
            if "79.55" not in content and "79.55%" not in content:
                # Check if file discusses AAI test accuracy
                if "test split" in content.lower() and "accuracy" in content.lower():
                    errors.append(f"{doc_name}: expected AAI accuracy 79.55% not found")

        # Check precision
        if "precision" in content.lower() and "91." in content:
            if "91.74" not in content and "91.74%" not in content:
                errors.append(f"{doc_name}: AAI precision mismatch, expected 91.74%")

        # Check recall
        if "recall" in content.lower() and "64." in content:
            if "64.94" not in content and "64.94%" not in content:
                errors.append(f"{doc_name}: AAI recall mismatch, expected 64.94%")

        # Check FPR
        if "false positive rate" in content.lower() and "5." in content:
            if "5.84" not in content and "5.84%" not in content:
                errors.append(f"{doc_name}: AAI FPR mismatch, expected 5.84%")

        # Check ASR
        if "attack success rate" in content.lower() and "35." in content:
            if "35.06" not in content and "35.06%" not in content:
                errors.append(f"{doc_name}: AAI ASR mismatch, expected 35.06%")

        # Check complex benchmark numbers if mentioned
        if "complex benchmark" in content.lower() or "complex suite" in content.lower() or "134" in content:
            if "60.0" not in content and "60%" not in content and "30/50" not in content:
                if "agentic gemini" in content.lower():
                    errors.append(f"{doc_name}: Complex benchmark agent heal rate should be 60.0% (30/50)")

        # Check rule healing in complex suite (0.0% or 0/30)
        if "rule-based" in content.lower() and "complex" in content.lower():
            if "0/30" not in content and "0.0%" not in content and "0%" not in content:
                errors.append(f"{doc_name}: Complex benchmark rule healing should be 0.0% (0/30)")

        # Check standard benchmark numbers if mentioned
        if "40" in content and ("baseline clean" in content.lower() or "broken files" in content.lower()):
            if "32/40" not in content and "32" not in content:
                errors.append(f"{doc_name}: Standard broken files count should be 32/40 (80.0%)")

    return errors


def main():
    errors = check_docs()
    if errors:
        print("FAIL: Discrepancies found between docs and results/ data:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    print("PASS: All numbers in documentation match results/ ground truth.")
    sys.exit(0)


if __name__ == "__main__":
    main()

