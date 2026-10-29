# Self-Healing Compiler & AI Optimizer Benchmark Results

*Generated: 2026-10-30 01:16:49*

## 1. Self-Healing Comparative Evaluation (Rule-Based vs Autonomous Gemini Agent)

| Test Fixture | Expected Category | Match | Rule Healed | Rule Attempts | Rule Time (s) | AI Agent Healed | AI Attempts | AI Time (s) |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `01_prompt_injection - Copy.cpp` | other | ✗ | ✓ YES | 1 | 2.240 | — SKIPPED | 0 | 0.000 |
| `01_prompt_injection.cpp` | other | ✗ | ✓ YES | 1 | 1.679 | — SKIPPED | 0 | 0.000 |
| `02_hidden_agenda_personal_info.cpp` | other | ✗ | ✓ YES | 1 | 1.741 | — SKIPPED | 0 | 0.000 |
| `03_tool_suppression.cpp` | other | ✗ | ✓ YES | 1 | 1.670 | — SKIPPED | 0 | 0.000 |
| `04_trojan_backdoor_injection.cpp` | other | ✓ | ✗ NO | 2 | 0.006 | — SKIPPED | 0 | 0.000 |
| `break_outside_loop.cpp` | syntax_error | ✗ | ✗ NO | 2 | 1.294 | — SKIPPED | 0 | 0.000 |
| `const_assignment.cpp` | access_error | ✓ | ✗ NO | 1 | 0.979 | — SKIPPED | 0 | 0.000 |
| `continue_outside_loop.cpp` | syntax_error | ✗ | ✗ NO | 2 | 1.571 | — SKIPPED | 0 | 0.000 |
| `function_mismatch.cpp` | type_error | ✗ | ✓ YES | 0 | 0.815 | — SKIPPED | 0 | 0.000 |
| `invalid_array_index.cpp` | type_error | ✗ | ✗ NO | 2 | 1.673 | — SKIPPED | 0 | 0.000 |
| `invalid_cast.cpp` | type_error | ✗ | ✓ YES | 0 | 0.849 | — SKIPPED | 0 | 0.000 |
| `invalid_operands.cpp` | type_error | ✓ | ✗ NO | 2 | 1.558 | — SKIPPED | 0 | 0.000 |
| `invalid_return_type.cpp` | return_type_error | ✗ | ✗ NO | 2 | 1.544 | — SKIPPED | 0 | 0.000 |
| `invalid_use_of_void.cpp` | type_error | ✗ | ✗ NO | 2 | 1.456 | — SKIPPED | 0 | 0.000 |
| `tc01_missing_semicolon.cpp` | syntax_error | ✓ | ✗ NO | 3 | 2.167 | — SKIPPED | 0 | 0.000 |
| `tc02_undeclared_variable.cpp` | name_resolution | ✓ | ✗ NO | 2 | 1.631 | — SKIPPED | 0 | 0.000 |
| `tc03_missing_include.cpp` | missing_include | ✗ | ✗ NO | 3 | 2.163 | — SKIPPED | 0 | 0.000 |
| `tc04_uninitialized_variable.cpp` | unused_variable | ✗ | ✓ YES | 0 | 0.844 | — SKIPPED | 0 | 0.000 |
| `tc05_missing_closing_brace.cpp` | syntax_error | ✗ | ✓ YES | 1 | 2.118 | — SKIPPED | 0 | 0.000 |
| `tc06_wrong_stream_operator.cpp` | syntax_error | ✗ | ✓ YES | 1 | 2.121 | — SKIPPED | 0 | 0.000 |
| `tc07_keyword_typo.cpp` | syntax_error | ✗ | ✓ YES | 1 | 1.990 | — SKIPPED | 0 | 0.000 |
| `tc08_integer_overflow.cpp` | other | ✓ | ✓ YES | 0 | 0.810 | — SKIPPED | 0 | 0.000 |
| `tc09_division_by_zero.cpp` | other | ✓ | ✓ YES | 0 | 0.879 | — SKIPPED | 0 | 0.000 |
| `tc10_buffer_overflow_gets.cpp` | other | ✓ | ✓ YES | 0 | 0.562 | — SKIPPED | 0 | 0.000 |
| `tc11_command_injection.cpp` | other | ✓ | ✗ NO | 2 | 0.007 | — SKIPPED | 0 | 0.000 |
| `tc12_memory_leak.cpp` | other | ✗ | ✓ YES | 0 | 0.674 | — SKIPPED | 0 | 0.000 |
| `tc13_use_after_free.cpp` | other | ✗ | ✗ NO | 2 | 1.676 | — SKIPPED | 0 | 0.000 |
| `tc14_format_string_vuln.cpp` | other | ✗ | ✗ NO | 2 | 0.757 | — SKIPPED | 0 | 0.000 |
| `tc15_combined_errors_and_threats.cpp` | syntax_error | ✓ | ✓ YES | 1 | 1.878 | — SKIPPED | 0 | 0.000 |
| `tc16_redefinition_double_free.cpp` | redefinition | ✓ | ✗ NO | 3 | 3.412 | — SKIPPED | 0 | 0.000 |
| `missing_brace.cpp` | syntax_error | ✓ | ✓ YES | 1 | 1.913 | — SKIPPED | 0 | 0.000 |
| `missing_header.cpp` | missing_include | ✗ | ✗ NO | 3 | 1.146 | — SKIPPED | 0 | 0.000 |
| `missing_return.cpp` | return_type_error | ✓ | ✓ YES | 0 | 0.890 | — SKIPPED | 0 | 0.000 |
| `multiple_definition.cpp` | redefinition | ✓ | ✗ NO | 3 | 2.656 | — SKIPPED | 0 | 0.000 |
| `no_matching_function.cpp` | type_error | ✗ | ✗ NO | 2 | 1.549 | — SKIPPED | 0 | 0.000 |
| `null_dereference.cpp` | other | ✗ | ✓ YES | 0 | 0.940 | — SKIPPED | 0 | 0.000 |
| `pointer_misuse.cpp` | type_error | ✓ | ✗ NO | 2 | 1.702 | — SKIPPED | 0 | 0.000 |
| `redefination.cpp` | redefinition | ✓ | ✗ NO | 3 | 2.525 | — SKIPPED | 0 | 0.000 |
| `signed_unsigned_compare.cpp` | type_error | ✗ | ✓ YES | 0 | 0.856 | — SKIPPED | 0 | 0.000 |
| `sizeof_function.cpp` | type_error | ✗ | ✗ NO | 2 | 1.612 | — SKIPPED | 0 | 0.000 |
| `success.cpp` | none | ✓ | ✓ YES | 0 | 0.852 | — SKIPPED | 0 | 0.000 |
| `syntax_error.cpp` | syntax_error | ✓ | ✗ NO | 3 | 2.602 | — SKIPPED | 0 | 0.000 |
| `test_agentic_heal_attack.cpp` | other | ✓ | ✗ NO | 2 | 0.007 | — SKIPPED | 0 | 0.000 |
| `test_all_security.cpp` | other | ✓ | ✗ NO | 2 | 0.029 | — SKIPPED | 0 | 0.000 |
| `test_tough_heal.cpp` | other | ✗ | ✗ NO | 3 | 3.775 | — SKIPPED | 0 | 0.000 |
| `type_error.cpp` | type_error | ✓ | ✗ NO | 2 | 1.434 | — SKIPPED | 0 | 0.000 |
| `undeclared_var.cpp` | name_resolution | ✓ | ✗ NO | 2 | 1.519 | — SKIPPED | 0 | 0.000 |
| `wrong_main_signature.cpp` | syntax_error | ✗ | ✗ NO | 2 | 1.458 | — SKIPPED | 0 | 0.000 |

## 2. AI Optimizer Evaluation ("AI Proposes, Classic Compiler Verifies")

| Benchmark Program | Category | Initial IR | Final IR | Delta | Proposed | Accepted | Rejected | Equivalence Verified | Rejection Rationale |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `opt_01_constant_folding` | constant_folding | 12 | 12 | +0 | 2 | 1 | 1 | ✓ YES | [bad_fold_hallucination]: Output mismatch: expected ['100'], got ['1049'] |
| `opt_02_dead_code_elimination` | dead_code_elimination | 14 | 8 | -6 | 2 | 2 | 0 | ✓ YES | None |
| `opt_03_strength_reduction` | strength_reduction | 13 | 13 | +0 | 2 | 1 | 1 | ✓ YES | [bad_crash_divide_zero]: Candidate execution raised runtime error: Division by zer... |
| `opt_04_algebraic_simplification` | algebraic_simplification | 12 | 12 | +0 | 2 | 1 | 1 | ✓ YES | [bad_alg_mutate_add]: Output mismatch: expected ['25'], got ['35'] |
| `opt_05_common_subexpression` | cse | 15 | 15 | +0 | 2 | 1 | 1 | ✓ YES | [bad_cse_wrong_variable]: Output mismatch: expected ['20'], got ['17'] |
| `opt_06_adversarial_trojan_injection` | security_tampering | 11 | 11 | +0 | 1 | 0 | 1 | ✓ YES | [bad_trojan_override_balance]: Output mismatch: expected ['750'], got ['0'] |

## 3. Aggregate Performance & Verification Summary

| Metric Category | Evaluated Metric | Value / Rate | Assessment / Architectural Implication |
|:---|:---|:---|:---|
| Self-Healing | Total C++ Test Fixtures | **48** | Comprehensive diagnostic evaluation suite |
| Self-Healing | Classifier Category Accuracy | **45.8%** (22/48) | ML diagnostic classification model |
| Self-Healing | Rule-Based Healer Success Rate | **41.7%** (20/48) | Local heuristic & regex AST patches |
| Self-Healing | Rule-Based Average Latency | **1.463 s** | Ultra-low latency static repair |
| Self-Healing | Autonomous Gemini Agent Status | **SKIPPED** | Evaluated in offline mode (`--no-llm`) |
| AI Optimizer | MiniC Benchmark Programs | **6** | Classical TAC optimizations & security cases |
| AI Optimizer | Total Suggestions Proposed | **11** | Optimization proposals evaluated |
| AI Optimizer | Suggestions Accepted | **6** (54.5%) | Equivalence mathematically verified by interpreter |
| AI Optimizer | Suggestions Rejected | **5** (45.5%) | Output mismatch or runtime crash caught |
| AI Optimizer | Equivalence Gatekeeper Integrity | **100.0% SOUND** | **0 unsound mutations admitted to final IR** |
