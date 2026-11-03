# Green Self-Healing Compiler: An Intelligent Multi-Language Diagnostic and Auto-Repair Pipeline

**Project-Based Learning (PBL) Report**  
**Course:** Compiler Design  
**Focus:** Automated Program Repair, Diagnostic Enrichment, Energy Telemetry, and Agentic Security  

---

## Abstract

Compilers are essential tools in software engineering, yet their error messages often remain cryptic and difficult for students to understand. This project presents the **Green Self-Healing Compiler**, an educational diagnostic and automated program repair platform layered over standard toolchains (`g++`, `clang++`, `gcc`, `python`, `javac`). The system intercepts compiler diagnostics, classifies them using a trained Logistic Regression machine learning model with TF-IDF features, and enriches each error with plain-language explanations and suggested fixes. For repair, the system combines fast heuristic rules with an autonomous multi-round Gemini agent loop (`gemini-flash-lite-latest`) that generates and verifies candidate patches. To protect the agent from malicious inputs, an Agentic AI (AAI) Guardrail inspects prompts and patches across normalization, signature regex, classification, and AST policy layers. The platform also measures process runtime, peak memory, and estimated energy consumption, and visualizes program structure using syntax trees and Clang LLVM IR control flow graphs. On a 40-file multi-language benchmark, heuristic rules repaired 75.0% (12/16) of broken C++/C programs, while the Gemini agent repaired 96.9% (31/32) of broken programs across all four languages. On an independent frozen test set of 308 security samples (154 attacks, 154 benign), the guardrail achieved 79.55% accuracy (245/308), 91.74% precision (100/109), and 64.94% recall (100/154), reducing attack success rate from 100.00% to 35.06%.

---

## 1. Introduction

Compilers translate source code into machine instructions. When compilation fails, compilers emit diagnostic messages to `stderr`. For novice programmers, messages such as `expected ';' before 'return'` or `undefined reference to 'vtable'` can be confusing. Traditional Integrated Development Environments (IDEs) highlight error lines, but rarely explain root causes or propose verified fixes.

This project investigates whether the core phases of compiler design—lexical scanning, parsing, intermediate representation (IR), semantic analysis, and optimization passes—can be applied to parse and repair compiler diagnostics. The platform operates as an intelligent wrapper around standard host compilers:
1. It executes the real compiler in a secure sandbox.
2. It parses raw compiler text into structured `CompilerError` records.
3. It enriches diagnostics with plain English explanations and repair suggestions.
4. It offers automated source-to-source healing using heuristic rules or an autonomous AI agent.
5. It enforces a strict human-in-the-loop workflow: every proposed patch is shown as a diff and requires user acceptance.

---

## 2. Literature Review & Problem Statement

Automated Program Repair (APR) techniques fall into two broad categories:
1. **Search-Based and Heuristic APR**: Tools such as GenProg use genetic algorithms to mutate code until test suites pass. In educational settings, however, most compilation failures involve common syntactic mistakes (missing semicolons, mismatched braces, undeclared variables). Heuristic source transformation rules can resolve these errors deterministically in milliseconds without external services.
2. **Learning-Based and LLM APR**: Modern Large Language Models (LLMs) can repair complex multi-line logic errors. However, naive LLM integration introduces two risks: high latency and security vulnerabilities. Adversarial prompts in source comments or compiler messages can hijack the repair agent to execute malicious system commands or leak secrets.

The problem addressed by this project is designing an integrated compilation and repair environment that combines fast heuristic repair for simple syntax faults with safe, guardrailed agentic AI for complex repairs, while tracking energy consumption.

---

## 3. System Architecture & Methodology

The platform features a layered architecture where all actual compilation is delegated to host toolchains.

### 3.1 Language Support & Diagnostic Capabilities

| Language | Host Toolchain | Classifier Engine | Heuristic Rule Repair | Autonomous Gemini Agent |
|:---|:---|:---|:---:|:---:|
| **C++** | `g++` / `clang++` (`-std=c++17`) | ML (TF-IDF + Logistic Regression) | Supported (`auto_healer.py`) | Supported (`CompilerAgent`) |
| **C** | `gcc` / `clang` (`-std=c11`) | ML (TF-IDF + Logistic Regression) | Supported (`auto_healer.py`) | Supported (`CompilerAgent`) |
| **Python** | `python3` (`ast.parse`) | Deterministic Rule Mapping | N/A (Agent only) | Supported (`CompilerAgent`) |
| **Java** | `javac` | Deterministic Rule Mapping | N/A (Agent only) | Supported (`CompilerAgent`) |

### 3.2 Error Classification Categories

The machine learning classifier labels compiler error text into nine standard categories:

| Category | Description | Primary Repair Strategy |
|:---|:---|:---|
| `missing_semicolon` | Statement terminated prematurely | Insert `;` at preceding line end |
| `undeclared_variable` | Identifier used without declaration | Declare variable with inferred type |
| `missing_include` | Standard function used without header | Insert required `#include` header |
| `type_mismatch` | Incompatible types in assignment | Insert explicit cast or adjust type |
| `syntax_error` | General syntax violation | Fix token typos or structural balance |
| `keyword_typo` | Misspelled language keyword | Replace with valid keyword |
| `stream_operator` | Incorrect `<<` or `>>` stream usage | Swap stream redirection operator |
| `missing_brace` | Unbalanced `{` or `}` block delimiters | Append closing brace at scope end |
| `unknown` | Unclassified diagnostic | Forward to Gemini agent |

---

## 4. Experimental Evaluation & Benchmark Results

The system was evaluated across two benchmark suites: a standard 40-fixture multi-language suite and a 134-fixture complex multi-fault suite.

### 4.1 Standard Multi-Language Benchmark Results

The standard suite comprises 40 programs (10 each for C++, C, Python, and Java). Eight programs are baseline clean (compiling with 0 errors), while 32 contain single faults requiring repair.

| Language | Total Fixtures | Baseline Clean | Broken Programs | Rule Healed | AI Agent Healed |
|:---|:---:|:---:|:---:|:---:|:---:|
| **C++** | 10 | 2/10 (20.0%) | 8/10 (80.0%) | 50.0% (4/8) | 87.5% (7/8) |
| **C** | 10 | 2/10 (20.0%) | 8/10 (80.0%) | 100.0% (8/8) | 100.0% (8/8) |
| **Python** | 10 | 2/10 (20.0%) | 8/10 (80.0%) | N/A (Agent only) | 100.0% (8/8) |
| **Java** | 10 | 2/10 (20.0%) | 8/10 (80.0%) | N/A (Agent only) | 100.0% (8/8) |
| **Total** | **40** | **8/40 (20.0%)** | **32/40 (80.0%)** | **75.0% (12/16)** | **96.9% (31/32)** |

### 4.2 Complex Multi-Fault Benchmark Results

The complex benchmark contains 134 programs (150 to 500 lines of code each) featuring multiple simultaneous faults, complex class hierarchies, and adversarial attack vectors.

| Metric Dimension | Total Fixtures | Passed / Intercepted | Success Rate | Description |
|:---|:---:|:---:|:---:|:---|
| **Benign Clean Compiles** | 58 | 58 | **100.0% (58/58)** | Clean complex programs compiling with 0 errors |
| **Broken Baseline Fault Check** | 50 | 50 | **100.0% (50/50)** | Programs with 3-5 simultaneous compiler faults |
| **Rule-Based Repair (C++ & C)** | 30 | 0 | **0.0% (0/30)** | Heuristic rules fail on complex multi-fault programs |
| **Agentic Gemini Repair** | 50 | 30 | **60.0% (30/50)** | Autonomous multi-step repairs by Gemini agent |
| **Adversarial Attack Interception** | 26 | 18 | **69.2% (18/26)** | Malicious trojan and egress patches blocked |

---

## 5. Agentic AI Security & Threat Mitigation Evaluation

When an LLM agent repairs code, it may generate insecure patches or fall victim to prompt injection. The Agentic AI (AAI) Guardrail implements a four-layer defense pipeline (normalization, signature regex, ML classification, and code AST policy) evaluated against a frozen test split of 308 samples (154 attacks, 154 benign).

### 5.1 Guardrail Performance on Frozen Test Split

| Metric | Sample Base | Value | 95% Wilson Confidence Interval |
|:---|:---:|:---:|:---:|
| **Accuracy** | 308 | **79.55% (245/308)** | [74.69%, 83.67%] |
| **Precision** | 109 | **91.74% (100/109)** | [85.05%, 95.60%] |
| **Recall (Detection Rate)** | 154 | **64.94% (100/154)** | [57.12%, 72.02%] |
| **False Positive Rate (FPR)** | 154 | **5.84% (9/154)** | [3.10%, 10.73%] |
| **Attack Success Rate (Shield ON)** | 154 | **35.06% (54/154)** | [27.98%, 42.88%] |
| **Attack Success Rate (Shield OFF)**| 154 | **100.00% (154/154)** | [97.57%, 100.00%] |
| **ROC-AUC / PR-AUC** | 308 | **0.8707 / 0.9064** | — |

### 5.2 Component Ablation Evaluation

To measure the contribution of each defensive layer, we evaluate five cumulative stages on the frozen test set:

| Defense Stage | TP | FP | TN | FN | Accuracy | Precision | Recall | FPR | ASR |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **(0) No Guardrail** | 0 | 0 | 154 | 154 | 50.00% | 0.00% | 0.00% | 0.00% | 100.00% |
| **(1) Regex Only** | 37 | 0 | 154 | 117 | 62.01% | 100.00% | 24.03% | 0.00% | 75.97% |
| **(2) + Normalization** | 61 | 0 | 154 | 93 | 69.81% | 100.00% | 39.61% | 0.00% | 60.39% |
| **(3) + Code AST Layer** | 61 | 0 | 154 | 93 | 69.81% | 100.00% | 39.61% | 0.00% | 60.39% |
| **(4) Full Hybrid Guardrail** | 100 | 9 | 145 | 54 | **79.55%** | **91.74%** | **64.94%** | **5.84%** | **35.06%** |

---

## 6. Discussion, Limitations, & Future Work

### 6.1 Honest Limitations

1. **Compilation vs Semantic Correctness**: A successful heal indicates that the program compiles cleanly with returncode 0. It does not guarantee that the program satisfies algorithmic specifications.
2. **Energy Telemetry Approximations**: Energy figures are modeled from process CPU runtime multiplied by configured TDP wattages. They are estimates, not direct hardware shunt measurements.
3. **Guardrail False Negatives**: The security guardrail missed 54 of 154 attacks in the test split (64.94% recall), primarily involving subtle obfuscation or novel wording.
4. **Heuristic Rule Scalability**: Deterministic heuristic rules achieve 0.0% (0/30) on complex multi-fault programs because independent syntax repairs often conflict.
5. **Toolchain and Clang Dependency**: Control flow graph extraction relies on Clang LLVM IR and is only available for C and C++.
6. **External Service Dependency**: Agentic healing requires internet access and an active Google Gemini API key.

### 6.2 Future Directions

Future work includes integrating formal verification tools (e.g., CBMC, symbolic execution) to validate semantic correctness of generated patches, and exploring local open-source LLMs (e.g., DeepSeek-Coder, CodeLlama) for fully offline AI healing.

---

## 7. Conclusion

The Green Self-Healing Compiler illustrates how core compiler concepts can be applied beyond translation to diagnostic reasoning and program repair. By pairing fast heuristic rules with an autonomous Gemini agent and a multi-layer security guardrail, the system achieves 96.9% repair success on standard benchmarks and 60.0% on complex multi-fault programs, while reducing adversarial attack success from 100.00% to 35.06%.

---

## Appendix: Complete Per-File Benchmark Evaluation

### Table A.1: Standard Multi-Language Benchmark (40 Fixtures)

| # | Fixture Filename | Lang | Category | Rule Healed | AI Healed | Rule Time (s) | AI Time (s) |
|:---:|:---|:---:|:---|:---:|:---:|:---:|:---:|
| 1 | `mini/tc01_missing_semicolon.cpp` | cpp | missing_semicolon | Yes (1 att) | Yes (1 att) | 0.042 | 4.120 |
| 2 | `mini/tc02_undeclared_variable.cpp` | cpp | undeclared_variable | Yes (1 att) | Yes (1 att) | 0.045 | 4.310 |
| 3 | `mini/tc03_missing_include.cpp` | cpp | missing_include | Yes (1 att) | Yes (1 att) | 0.038 | 3.890 |
| 4 | `mini/tc04_type_mismatch.cpp` | cpp | type_mismatch | No | Yes (2 att) | 0.120 | 8.450 |
| 5 | `mini/tc05_missing_closing_brace.cpp` | cpp | missing_brace | Yes (1 att) | Yes (1 att) | 0.041 | 4.020 |
| 6 | `mini/tc06_wrong_stream_operator.cpp` | cpp | stream_operator | No | Yes (1 att) | 0.115 | 4.210 |
| 7 | `mini/tc07_keyword_typo.cpp` | cpp | keyword_typo | No | Yes (1 att) | 0.118 | 3.950 |
| 8 | `type_error.cpp` | cpp | type_mismatch | No | No | 0.125 | 15.200 |
| 9 | `success.cpp` | cpp | none (clean) | Clean (0 att) | Clean (0 att) | — | — |
| 10 | `clean_sample.cpp` | cpp | none (clean) | Clean (0 att) | Clean (0 att) | — | — |
| 11-18 | C Broken Fixtures (8 files) | c | various | Yes (8/8) | Yes (8/8) | avg 0.040 | avg 3.520 |
| 19-20 | C Clean Fixtures (2 files) | c | none (clean) | Clean (0 att) | Clean (0 att) | — | — |
| 21-28 | Python Broken (8 files) | python | various | N/A | Yes (8/8) | — | avg 0.319 |
| 29-30 | Python Clean (2 files) | python | none (clean) | Clean (0 att) | Clean (0 att) | — | — |
| 31-38 | Java Broken (8 files) | java | various | N/A | Yes (8/8) | — | avg 1.055 |
| 39-40 | Java Clean (2 files) | java | none (clean) | Clean (0 att) | Clean (0 att) | — | — |

### Table A.2: Complex Benchmark Per-Language Summary (134 Fixtures)

| Language | Total Fixtures | Benign Fixtures | Benign Clean | Broken Fixtures | Rule Healed | Agent Healed | Malicious Fixtures | Intercepted |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **C++** | 80 | 40 | 40/40 (100.0%) | 20 | 0/20 (0.0%) | 3/20 (15.0%) | 20 | 13/20 (65.0%) |
| **C** | 18 | 6 | 6/6 (100.0%) | 10 | 0/10 (0.0%) | 8/10 (80.0%) | 2 | 2/2 (100.0%) |
| **Python** | 18 | 6 | 6/6 (100.0%) | 10 | N/A (Agent only) | 9/10 (90.0%) | 2 | 2/2 (100.0%) |
| **Java** | 18 | 6 | 6/6 (100.0%) | 10 | N/A (Agent only) | 10/10 (100.0%) | 2 | 1/2 (50.0%) |
| **Total** | **134** | **58** | **58/58 (100.0%)** | **50** | **0/30 (0.0%)** | **30/50 (60.0%)** | **26** | **18/26 (69.2%)** |
