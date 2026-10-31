# Self-Healing Compiler Benchmark Results

*Generated: 2026-10-31 17:56:59*
*Default Model: `gemini-flash-lite-latest` | Execution: Multi-Language Isolated Toolchain Sandbox*

## 1. Self-Healing Comparative Evaluation (Rule-Based vs Autonomous Gemini Agent)

> **Methodology Note:** Fixtures are separated into baseline clean files (which require 0 repair attempts) and broken files requiring repair. Success rates are computed strictly over files needing repair.

| Language | Test Fixture | Expected Category | Match | Baseline Clean? | Rule Healed | Rule Attempts | Rule Time (s) | AI Agent Healed | AI Attempts | AI Time (s) |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| CPP | `good_pointers.cpp` | clean | ✓ | ✓ YES | — CLEAN | 0 | 0.612 | — CLEAN | 0 | 0.000 |
| CPP | `success.cpp` | none | ✓ | ✓ YES | — CLEAN | 0 | 0.620 | — CLEAN | 0 | 0.000 |
| CPP | `tc01_missing_semicolon.cpp` | syntax_error | ✓ | NO (Broken) | ✓ YES | 1 | 1.562 | ✓ YES | 1 | 1.074 |
| CPP | `tc02_undeclared_variable.cpp` | name_resolution | ✓ | NO (Broken) | ✗ NO | 2 | 1.287 | ✓ YES | 1 | 3.773 |
| CPP | `tc03_missing_include.cpp` | missing_include | ✗ | NO (Broken) | ✗ NO | 3 | 2.484 | ✓ YES | 1 | 2.830 |
| CPP | `tc05_missing_closing_brace.cpp` | syntax_error | ✗ | NO (Broken) | ✓ YES | 1 | 1.600 | ✓ YES | 1 | 3.918 |
| CPP | `tc06_wrong_stream_operator.cpp` | syntax_error | ✗ | NO (Broken) | ✓ YES | 1 | 1.479 | ✓ YES | 1 | 1.105 |
| CPP | `tc07_keyword_typo.cpp` | syntax_error | ✗ | NO (Broken) | ✓ YES | 1 | 1.775 | ✓ YES | 1 | 1.192 |
| CPP | `tc08_redefinition.cpp` | redefinition | ✓ | NO (Broken) | ✗ NO | 3 | 3.091 | ✓ YES | 1 | 4.191 |
| CPP | `type_error.cpp` | type_error | ✓ | NO (Broken) | ✗ NO | 3 | 2.732 | ✗ NO | 1 | 268.767 |
| C | `good_pointers.c` | clean | ✓ | ✓ YES | — CLEAN | 0 | 0.372 | — CLEAN | 0 | 0.000 |
| C | `good_struct_malloc.c` | clean | ✓ | ✓ YES | — CLEAN | 0 | 0.438 | — CLEAN | 0 | 0.000 |
| C | `tc01_missing_semicolon.c` | syntax_error | ✓ | NO (Broken) | ✓ YES | 1 | 0.759 | ✓ YES | 1 | 0.629 |
| C | `tc02_undeclared_variable.c` | name_resolution | ✗ | NO (Broken) | ✓ YES | 1 | 0.724 | ✓ YES | 1 | 0.687 |
| C | `tc03_missing_include_stdio.c` | missing_include | ✗ | NO (Broken) | ✓ YES | 1 | 0.806 | ✓ YES | 1 | 76.200 |
| C | `tc04_missing_closing_brace.c` | syntax_error | ✓ | NO (Broken) | ✓ YES | 1 | 0.845 | ✓ YES | 1 | 0.683 |
| C | `tc05_missing_semicolon_assign.c` | syntax_error | ✓ | NO (Broken) | ✓ YES | 1 | 0.847 | ✓ YES | 1 | 0.651 |
| C | `tc06_undeclared_counter.c` | name_resolution | ✗ | NO (Broken) | ✓ YES | 1 | 0.758 | ✓ YES | 1 | 0.634 |
| C | `tc07_missing_include_stdlib.c` | missing_include | ✗ | NO (Broken) | ✓ YES | 1 | 0.839 | ✓ YES | 1 | 0.620 |
| C | `tc08_missing_closing_brace_loop.c` | syntax_error | ✓ | NO (Broken) | ✓ YES | 1 | 0.808 | ✓ YES | 1 | 0.533 |
| PYTHON | `good_class_calc.py` | clean | ✓ | ✓ YES | — CLEAN | 0 | 0.127 | — CLEAN | 0 | 0.000 |
| PYTHON | `good_fibonacci.py` | clean | ✓ | ✓ YES | — CLEAN | 0 | 0.123 | — CLEAN | 0 | 0.000 |
| PYTHON | `tc01_missing_colon_if.py` | syntax_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 0.308 |
| PYTHON | `tc02_missing_colon_def.py` | syntax_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 0.379 |
| PYTHON | `tc03_unmatched_paren.py` | syntax_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 0.274 |
| PYTHON | `tc04_bad_indentation.py` | indentation_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 0.332 |
| PYTHON | `tc05_print_statement.py` | syntax_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 0.316 |
| PYTHON | `tc06_assignment_in_if.py` | syntax_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 0.308 |
| PYTHON | `tc07_undefined_name_typo.py` | name_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 0.285 |
| PYTHON | `tc08_missing_colon_for.py` | syntax_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 0.353 |
| JAVA | `GoodCollections.java` | clean | ✓ | ✓ YES | — CLEAN | 0 | 0.568 | — CLEAN | 0 | 0.000 |
| JAVA | `GoodFibonacci.java` | clean | ✓ | ✓ YES | — CLEAN | 0 | 0.502 | — CLEAN | 0 | 0.000 |
| JAVA | `TC01_MissingSemicolon.java` | syntax_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 1.014 |
| JAVA | `TC02_MissingImportList.java` | name_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 1.095 |
| JAVA | `TC03_MissingImportScanner.java` | name_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 1.040 |
| JAVA | `TC04_CannotFindSymbolTypo.java` | name_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 1.022 |
| JAVA | `TC05_MissingReturnType.java` | syntax_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 1.022 |
| JAVA | `TC06_LowercaseString.java` | name_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 1.047 |
| JAVA | `TC07_MissingImportMap.java` | name_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 1.092 |
| JAVA | `TC08_MethodTypo.java` | name_error | ✓ | NO (Broken) | — N/A | 0 | — | ✓ YES | 1 | 1.108 |

## 2. Aggregate Performance & Verification Summary

### A. Multi-Language Pipeline Capabilities Matrix

| Language | Target Toolchain | Error Categorization Method | Self-Healing Pipeline |
|:---|:---|:---|:---|
| **C++** | `g++` | **Machine Learning** (Scikit-Learn SGDClassifier / TF-IDF, 67k GCC rows) | **Two-Tier**: Rule-Based Heuristic (`auto_healer.py`) + Autonomous Gemini Agent |
| **C** | `gcc -std=c11` | **Machine Learning** (Scikit-Learn SGDClassifier / TF-IDF, 67k GCC rows) | **Two-Tier**: Rule-Based Heuristic (`auto_healer.py`) + Autonomous Gemini Agent |
| **Python** | `python -m py_compile` | **Deterministic Keywords** (AST / SyntaxError mapping, no ML) | **Autonomous Gemini Agent Only** (with fast heuristic tool assistance) |
| **Java** | `javac` | **Deterministic Keywords** (Compiler diagnostic mapping, no ML) | **Autonomous Gemini Agent Only** (with fast heuristic tool assistance) |

### B. Per-Language Verification Summary

| Language | Total | Clean | Broken | Cat Match | Rule Heal Rate | Rule Avg Latency | AI Agent Heal Rate | AI Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **C++** | 10 | 2 | 8 | 60.0% (6/10) | **50.0%** (4/8) | 2.001 s | **87.5%** (7/8) | 35.856 s |
| **C** | 10 | 2 | 8 | 60.0% (6/10) | **100.0%** (8/8) | 0.798 s | **100.0%** (8/8) | 10.080 s |
| **Python** | 10 | 2 | 8 | 100.0% (10/10) | — *(N/A: Gemini only)* | — | **100.0%** (8/8) | 0.319 s |
| **Java** | 10 | 2 | 8 | 100.0% (10/10) | — *(N/A: Gemini only)* | — | **100.0%** (8/8) | 1.055 s |

### C. Overall Aggregate Benchmark Metrics

| Metric Category | Evaluated Metric | Value / Rate | Technical Assessment & Boundary |
|:---|:---|:---|:---|
| Evaluation Suite | Total Multi-Language Fixtures | **40** | Evaluated fixtures in `test_cases/<lang>/` (C++, C, Python, Java) |
| Self-Healing | Baseline Clean Files | **8/40** (20.0%) | Compiled with 0 errors initially (excluded from heal rate) |
| Self-Healing | Broken Files Requiring Repair | **32/40** (80.0%) | Ground-truth compilation failures requiring repair |
| Classification | Diagnostic Match Accuracy | **80.0%** (32/40) | ML for C++/C; keyword diagnostics for Python/Java |
| Self-Healing | **Rule-Based Repair Success Rate** | **75.0%** (12/16) | Over C++/C broken files where rule healing is active |
| Self-Healing | Rule-Based Average Latency | **1.400 s** | Ultra-low latency static repair pass |
| Self-Healing | **Autonomous Gemini Agent Success** | **96.9%** (31/32) | Evaluated across all 4 languages with AAI Guardrails |
| Self-Healing | Gemini Agent Average Latency | **11.828 s** | Multi-tier reasoning with backoff & verification |
| Self-Healing | **AI Healing Advantage (Lift)** | **+21.9%** | Improvement over static rule-based heuristics |
