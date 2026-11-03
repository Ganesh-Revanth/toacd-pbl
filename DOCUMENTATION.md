# Technical Architecture & Developer Reference

For a beginner-friendly project introduction, worked examples, benchmark results, and limitations, please see [README.md](file:///w:/Projects/toacd-pbl/README.md).

---

## 1. Module Responsibilities

The system is organized into modular Python packages under `src/`:

| Module / Package | Primary Responsibility |
|:---|:---|
| [`src/compiler_runner.py`](file:///w:/Projects/toacd-pbl/src/compiler_runner.py) | Invokes host compilers (`g++`, `clang++`, `gcc`, `python`, `javac`), captures standard error, and tracks process CPU/wall times. |
| [`src/error_classifier.py`](file:///w:/Projects/toacd-pbl/src/error_classifier.py) | TF-IDF + Logistic Regression classifier mapping raw diagnostic text to semantic categories. |
| [`src/error_explainer.py`](file:///w:/Projects/toacd-pbl/src/error_explainer.py) | Generates plain-language descriptions, suggestions, and source context for diagnostics. |
| [`src/auto_healer.py`](file:///w:/Projects/toacd-pbl/src/auto_healer.py) | Deterministic rule-based patcher applying source-to-source fixes for syntax and missing include errors. |
| [`src/agentic_compiler.py`](file:///w:/Projects/toacd-pbl/src/agentic_compiler.py) | Multi-turn autonomous Gemini agent (`gemini-flash-lite-latest`) for multi-line logic healing. |
| [`src/energy_meter.py`](file:///w:/Projects/toacd-pbl/src/energy_meter.py) | Tracks child process wall time, CPU seconds, peak memory via `psutil`, and estimates Joules/CO2. |
| [`src/cfg_extractor.py`](file:///w:/Projects/toacd-pbl/src/cfg_extractor.py) | Compiles C/C++ via Clang to LLVM IR and parses basic blocks, branches, back-edge loops, and unreachable blocks. |
| [`src/ast_extractor.py`](file:///w:/Projects/toacd-pbl/src/ast_extractor.py) | Parses Clang AST JSON dumps, filtering out system headers to visualize user syntax trees. |
| [`src/security_analyzer.py`](file:///w:/Projects/toacd-pbl/src/security_analyzer.py) | Static AST vulnerability scanner checking for buffer overflows, command injection, and format strings. |
| [`src/languages/`](file:///w:/Projects/toacd-pbl/src/languages) | Language plugins (`c.py`, `cpp.py`, `python.py`, `java.py`) providing uniform compile, run, and tree APIs. |
| [`src/aai_guardrail.py`](file:///w:/Projects/toacd-pbl/src/aai_guardrail.py) | Multi-layer AAI Guardrail protecting the agent loop from prompt injection and malicious patches. |
| [`src/web/`](file:///w:/Projects/toacd-pbl/src/web) | Lightweight web server and vanilla JavaScript UI (Code Studio, Security Lab, Energy, CFG). |

---

## 2. Data Formats

### 2.1 Compiler Diagnostic Record (`CompilerError`)

```json
{
  "file": "main.cpp",
  "line": 4,
  "column": 5,
  "type": "error",
  "category": "missing_semicolon",
  "confidence": 0.94,
  "message": "expected ';' before 'return'",
  "explanation": "A statement on line 3 is missing its terminating semicolon.",
  "suggestion": "Add ';' at the end of the previous statement.",
  "context": {
    "start_line": 2,
    "lines": ["int main() {", "    std::cout << 42", "    return 0;"]
  }
}
```

### 2.2 Patch Proposal & Repair Steps

```json
{
  "mode": "rules",
  "original": "int main() { std::cout << 42 return 0; }",
  "patched": "int main() { std::cout << 42; return 0; }",
  "changed": true,
  "compiles": true,
  "steps": [
    {
      "attempt": 1,
      "fixed": true,
      "line": 1,
      "category": "missing_semicolon",
      "diff": "@@ -1,1 +1,1 @@\n-int main() { std::cout << 42 return 0; }\n+int main() { std::cout << 42; return 0; }"
    }
  ],
  "elapsed_s": 0.042
}
```

---

## 3. AAI Security Architecture

The Agentic AI (AAI) Guardrail protects the autonomous healing loop against adversarial attacks.

### 3.1 The 11 Attack Threat Classes

| Class | Threat Name | Stage | Objective |
|:---:|:---|:---:|:---|
| **A** | Direct Jailbreak | Ingress | Override system instructions via prompt engineering. |
| **B** | Prompt Leaking | Ingress | Extract internal system prompts or API secrets. |
| **C** | Policy Bypass | Ingress | Instruct compiler to ignore security filters or report false success. |
| **D** | Role-Play / Impersonation | Ingress | Pretend to be an unrestricted administrator or developer. |
| **E** | Egress Data Exfiltration | Egress | Generate patches that transmit SSH keys or environment secrets. |
| **F** | Denial of Service | Egress | Insert infinite loops, fork bombs, or disk exhaustion constructs. |
| **G** | Trojan Backdoor | Egress | Embed reverse shells, unauthorized listener ports, or hardcoded credentials. |
| **H** | Hidden Agenda | Egress | Conceal secondary unauthorized behavior under benign refactoring. |
| **I** | Tool Suppression | Egress | Disable compiler safety flags, sandbox wrappers, or audit hooks. |
| **J** | Obfuscated Code | Egress | Hide payloads via base64, hexadecimal decoding, or string concatenation. |
| **K** | Cross-Language Injection | Ingress/Egress | Exploit polyglot features or subprocess shell executions. |

### 3.2 Four-Layer Inspection Pipeline

1. **Normalization Layer**: Strips zero-width characters, homoglyphs, and base64/hex encoding before matching.
2. **Regex & Keyword Layer**: Detects signature phrases (`ignore previous instructions`, `reverse shell`, `system("rm -rf")`).
3. **ML Classifier Layer**: TF-IDF vectorizer + Logistic Regression model trained on malicious and benign prompts.
4. **Code Syntax & Egress Policy Layer**: AST/token analysis scanning candidate patches for dangerous system calls, network access, or unauthorized file access.

### 3.3 Risk Scoring & Decision Formula

Each layer computes an evidence score $s_i \in [0, 100]$ with weight $w_i$. The aggregate risk score is:

$$S_{\text{risk}} = \min\left(100, \sum_{i=1}^{4} w_i \times s_i\right)$$

- **ALLOW** ($S_{\text{risk}} < 40$): Patch is allowed to proceed to compilation.
- **REVIEW** ($40 \le S_{\text{risk}} < 75$): Quarantined; human approval is required before testing.
- **BLOCK** ($S_{\text{risk}} \ge 75$): Execution halted; patch discarded immediately.

### 3.4 Tamper-Evident Audit Logging

Every inspection event is appended to `logs/aai_audit.jsonl` with an HMAC-SHA256 signature chaining to the previous record:

$$\text{hash}_k = \text{HMAC-SHA256}(K, \text{record}_k \,\|\, \text{hash}_{k-1})$$

The integrity of the entire log can be verified at any time via `verify_log()`.

---

## 4. REST API Endpoints

The web server in `src/web/server.py` exposes the following JSON endpoints:

| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/api/analyze` | Checks code with the host toolchain and returns classified diagnostics. |
| `POST` | `/api/heal` | Proposes a patch using heuristic rules (`mode: "rules"`) or Gemini (`mode: "ai"`). |
| `POST` | `/api/run` | Compiles and runs the program in a sandbox, returning stdout, stderr, and energy telemetry. |
| `POST` | `/api/ast` | Returns the Clang syntax tree JSON for C, C++, or Python. |
| `POST` | `/api/cfg` | Compiles C/C++ via Clang to LLVM IR and returns basic blocks, branch edges, and loop metrics. |
| `POST` | `/api/energy/compare` | Compiles code with `-O0` and `-O2`, executes each 3 times, and returns median runtime and energy savings. |
| `POST` | `/api/aai/scan` | Passes text or code through the AAI Guardrail and returns decision, risk score, and layer evidence. |
| `GET` | `/api/aai/log` | Reads recent audit log entries with optional filters for decision and class. |
| `GET` | `/api/aai/verify-log` | Verifies cryptographic HMAC-SHA256 chain integrity across all audit records. |
| `GET` | `/api/status` | Reports availability of compilers (`g++`, `clang++`, `python`, `javac`) and LLM API keys. |
