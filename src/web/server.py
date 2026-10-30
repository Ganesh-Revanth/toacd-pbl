"""
server.py
---------
Local web UI for the Green Self-Healing Compiler.

Runs on Python's standard library only (no Flask/FastAPI needed) and reuses the
existing modules: error_explainer, auto_healer, diff_viewer, ast_extractor,
security_analyzer, agentic_compiler, and the MiniC core + AI packages.

Usage:
    python src/web/server.py                # http://127.0.0.1:8765
    python src/web/server.py --port 9000 --no-browser

Safety notes:
  * Binds to 127.0.0.1 only (never exposed to the network by default).
  * Request bodies are capped; compiler runs have timeouts and use temp dirs.
  * C++ programs only run when the user presses "Compile & Run" (/api/cpp/run).
    They run in a throw-away temp directory with a wall-clock timeout, an output
    cap, CPU / memory / file-size limits (POSIX) and a stripped environment, so
    API keys are not visible to them. This is a convenience limit for your own
    code on your own machine, NOT a security sandbox: do not run untrusted code.
    MiniC programs run inside the Python TAC interpreter, which has a step limit.
  * Healing endpoints only PROPOSE a patch. The browser shows the diff and the
    user accepts or rejects it; nothing is written to disk by the server.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

WEB_DIR = Path(__file__).resolve().parent
SRC_DIR = WEB_DIR.parent
ROOT_DIR = SRC_DIR.parent
STATIC_DIR = WEB_DIR / "static"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

MAX_BODY_BYTES = 1_000_000
COMPILE_TIMEOUT_S = 30
HEAL_ATTEMPTS = 3
RUN_TIMEOUT_S = 5
RUN_OUTPUT_CAP = 64 * 1024          # bytes kept per stream (stdout / stderr)
RUN_STDIN_CAP = 64 * 1024
BIN_NAME = "out.exe" if sys.platform == "win32" else "out.bin"

_ERR_PATTERN = re.compile(r"^(.+?):(\d+):(\d+):\s*(error|warning):\s*(.*)$")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

class ApiError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _load_env() -> None:
    try:
        from ai.llm_client import load_env_file
        load_env_file()
    except Exception:
        pass


def _mock_enabled() -> bool:
    return os.environ.get("LLM_MOCK", "").lower() in ("1", "true", "yes", "on")


def _api_key() -> Optional[str]:
    try:
        from ai.llm_client import get_stored_api_key
        return get_stored_api_key()
    except Exception:
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _require_llm() -> None:
    if not _api_key() and not _mock_enabled():
        raise ApiError(
            "No Gemini API key found. Set the GEMINI_API_KEY environment variable "
            "(or put it in a .env file) and restart the server. "
            "For an offline demo, start the server with LLM_MOCK=1.",
            status=412,
        )


def _to_jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _need_code(body: Dict[str, Any]) -> str:
    code = body.get("code")
    if not isinstance(code, str) or not code.strip():
        raise ApiError("Request needs a non-empty 'code' string.")
    if len(code) > 200_000:
        raise ApiError("Source code is too large (limit 200 KB).", status=413)
    return code


def diff_lines(original: str, patched: str, context: int = 3) -> List[Dict[str, Any]]:
    from diff_viewer import compute_diff
    return [
        {"old": d.line_no_old, "new": d.line_no_new, "kind": d.kind, "text": d.content}
        for d in compute_diff(original, patched, context)
    ]


# ──────────────────────────────────────────────────────────────────────────────
# C++ compile / analyze / heal
# ──────────────────────────────────────────────────────────────────────────────

_classifier_lock = threading.Lock()
_classifier: Any = None
_classifier_tried = False


def _get_classifier():
    global _classifier, _classifier_tried
    with _classifier_lock:
        if _classifier_tried:
            return _classifier
        _classifier_tried = True
        try:
            import warnings
            warnings.filterwarnings("ignore")
            from error_classifier import ErrorClassifier
            clf = ErrorClassifier()
            if clf.load():
                _classifier = clf
        except Exception:
            _classifier = None
        return _classifier


def _classify(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    clf = _get_classifier()
    for e in errors:
        if e.get("category"):
            continue
        cat, conf = "other", 0.5
        if clf is not None:
            try:
                c, p = clf.predict(e.get("message", ""))
                cat, conf = (c or "other"), float(p)
            except Exception:
                pass
        e["category"] = cat
        e["confidence"] = round(conf, 3)
    return errors


def compile_cpp(code: str, workdir: str) -> Tuple[List[Dict[str, Any]], str, str]:
    """Compile `code` with g++ inside workdir. Returns (errors, stderr, source_path)."""
    from compiler_runner import _sanitize_code, get_compiler_cmd_and_env

    src = os.path.join(workdir, "main.cpp")
    with open(src, "w", encoding="utf-8") as f:
        f.write(code)

    if not _sanitize_code(code):
        return ([{
            "file": src, "line": 1, "column": 1, "type": "error",
            "message": "Security Error: Malicious command injection or forbidden system call detected.",
            "raw": "error: Malicious code blocked",
            "category": "security_violation", "confidence": 1.0,
        }], "error: Malicious code blocked", src)

    gxx, env = get_compiler_cmd_and_env()
    # ASCII diagnostics: GCC prints curly quotes in UTF-8 locales, which breaks pattern matching.
    env = {**env, "LC_ALL": "C", "LANGUAGE": "C"}
    try:
        res = subprocess.run(
            [gxx, "-std=c++17", "-Wall", src, "-o", os.path.join(workdir, BIN_NAME)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
            cwd=workdir, timeout=COMPILE_TIMEOUT_S,
        )
    except FileNotFoundError:
        raise ApiError("g++ was not found on this machine. Install a C++ toolchain and restart.", 503)
    except subprocess.TimeoutExpired:
        return ([{
            "file": src, "line": 1, "column": 1, "type": "error",
            "message": f"Compilation timed out after {COMPILE_TIMEOUT_S}s.",
            "raw": "timeout", "category": "other", "confidence": 1.0,
        }], "timeout", src)

    errors: List[Dict[str, Any]] = []
    for line in res.stderr.splitlines():
        m = _ERR_PATTERN.match(line.strip())
        if m:
            errors.append({
                "file": m.group(1), "line": int(m.group(2)), "column": int(m.group(3)),
                "type": m.group(4), "message": m.group(5), "raw": line,
            })
    if res.returncode != 0 and not errors:
        first = res.stderr.strip().splitlines()[0] if res.stderr.strip() else "Compilation failed"
        errors.append({
            "file": src, "line": 1, "column": 1, "type": "error",
            "message": first, "raw": first, "category": "other", "confidence": 0.5,
        })
    return errors, res.stderr, src


def _enrich(errors: List[Dict[str, Any]], src_path: str) -> List[Dict[str, Any]]:
    """Add explanation, suggestion, context and security info using the existing explainer."""
    from models import CompilerError
    from error_explainer import enrich_error

    out = []
    for e in errors:
        ce = CompilerError(e.get("file") or src_path, e.get("line"), e.get("column"),
                           e.get("type", "error"), e.get("message", ""), e.get("raw", ""))
        try:
            enrich_error(ce)
        except Exception:
            pass
        d = ce.to_dict()
        d["file"] = "main.cpp"
        d["category"] = e.get("category") or d.get("category")
        if e.get("category"):
            d["confidence"] = e.get("confidence", d.get("confidence"))
        out.append(d)
    return out


def _security_findings(src_path: str) -> List[Dict[str, Any]]:
    try:
        from security_analyzer import analyze
        res = []
        for f in analyze(src_path, []):
            d = f.to_dict()
            d["file"] = "main.cpp"
            res.append(d)
        return res
    except Exception:
        return []


def _analyze_in(code: str, wd: str) -> Dict[str, Any]:
    """Compile `code` inside the existing directory `wd` and describe the result."""
    t0 = time.time()
    errors, stderr, src = compile_cpp(code, wd)
    _classify(errors)
    enriched = _enrich(errors, src)
    security = _security_findings(src)
    hard = sum(1 for e in enriched if e["type"] == "error")
    warn = sum(1 for e in enriched if e["type"] == "warning")
    return {
        "ok": hard == 0,
        "error_count": hard,
        "warning_count": warn,
        "diagnostics": enriched,
        "security": security,
        "raw_stderr": stderr.strip(),
        "elapsed_s": round(time.time() - t0, 3),
    }


def api_cpp_analyze(body: Dict[str, Any]) -> Dict[str, Any]:
    code = _need_code(body)
    with tempfile.TemporaryDirectory(prefix="webui_") as wd:
        return _analyze_in(code, wd)


def _run_env(workdir: str) -> Dict[str, str]:
    """A minimal environment: enough to run a program, nothing secret (no API keys)."""
    env = {"PATH": os.environ.get("PATH", ""), "HOME": workdir, "TMPDIR": workdir, "TEMP": workdir, "TMP": workdir}
    for k in ("SYSTEMROOT", "SystemRoot", "LANG", "LC_ALL"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def _signal_name(returncode: int) -> Optional[str]:
    if returncode >= 0 or sys.platform == "win32":
        return None
    import signal
    try:
        return signal.Signals(-returncode).name
    except ValueError:
        return f"signal {-returncode}"


_SIGNAL_HINTS = {
    "SIGSEGV": "Segmentation fault: the program touched memory it does not own (null pointer, bad index, deep recursion).",
    "SIGABRT": "Aborted: an assertion failed, an exception was not caught, or memory was freed twice.",
    "SIGFPE": "Arithmetic error, usually an integer division by zero.",
    "SIGKILL": "The program was killed (it probably used too much memory).",
    "SIGXCPU": "The program used too much CPU time.",
    "SIGXFSZ": "The program tried to write a file that was too large.",
}


def run_binary(binary: str, workdir: str, stdin_text: str) -> Dict[str, Any]:
    """Run a compiled program with a timeout and output cap. Never raises for program failures."""
    out_path, err_path, in_path = (os.path.join(workdir, n) for n in ("stdout.txt", "stderr.txt", "stdin.txt"))
    with open(in_path, "w", encoding="utf-8", newline="") as f:
        f.write(stdin_text)

    if sys.platform == "win32":
        cmd, extra = [binary], {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    else:
        # ulimit failures are ignored on purpose (e.g. -v is unsupported on some systems).
        script = ('ulimit -c 0 2>/dev/null; ulimit -t 10 2>/dev/null; ulimit -f 20480 2>/dev/null; '
                  'ulimit -v 2097152 2>/dev/null; exec "$0"')
        cmd, extra = ["/bin/sh", "-c", script, binary], {"start_new_session": True}

    timed_out = False
    flooded = False
    t0 = time.time()
    with open(in_path, "rb") as fin, open(out_path, "wb") as fout, open(err_path, "wb") as ferr:
        try:
            proc = subprocess.Popen(cmd, stdin=fin, stdout=fout, stderr=ferr, cwd=workdir,
                                    env=_run_env(workdir), **extra)
        except OSError as exc:
            return {"started": False, "error": f"Could not start the program: {exc}"}

        def kill() -> None:
            try:
                if sys.platform == "win32":
                    proc.kill()
                else:
                    import signal
                    os.killpg(proc.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass

        while proc.poll() is None:
            if time.time() - t0 > RUN_TIMEOUT_S:
                timed_out = True
                kill()
                break
            # Stop a program that floods its output long before the timeout.
            if os.path.getsize(out_path) + os.path.getsize(err_path) > 8 * RUN_OUTPUT_CAP:
                flooded = True
                kill()
                break
            time.sleep(0.01)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            kill()
    elapsed_ms = int((time.time() - t0) * 1000)

    def read_capped(path: str) -> Tuple[str, bool]:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            data = f.read(RUN_OUTPUT_CAP)
        return data.decode("utf-8", errors="replace"), size > RUN_OUTPUT_CAP

    stdout, out_cut = read_capped(out_path)
    stderr, err_cut = read_capped(err_path)
    rc = proc.returncode
    sig = _signal_name(rc) if rc is not None else None
    killed_by_us = timed_out or flooded
    return {
        "started": True,
        "stdout": stdout, "stderr": stderr,
        "truncated": out_cut or err_cut,
        "exit_code": rc, "signal": None if killed_by_us else sig,
        "signal_hint": None if killed_by_us else _SIGNAL_HINTS.get(sig or ""),
        "timed_out": timed_out, "output_flood": flooded, "timeout_s": RUN_TIMEOUT_S,
        "elapsed_ms": elapsed_ms,
        "used_stdin": bool(stdin_text),
    }


def api_cpp_run(body: Dict[str, Any]) -> Dict[str, Any]:
    """Compile and, when there are no errors, run the program. Compile problems come back as in /analyze."""
    code = _need_code(body)
    stdin_text = body.get("stdin", "")
    if not isinstance(stdin_text, str):
        raise ApiError("'stdin' must be a string.")
    if len(stdin_text.encode("utf-8")) > RUN_STDIN_CAP:
        raise ApiError("Program input is too large (limit 64 KB).", status=413)
    with tempfile.TemporaryDirectory(prefix="webui_run_") as wd:
        analysis = _analyze_in(code, wd)
        binary = os.path.join(wd, BIN_NAME)
        if not analysis["ok"] or not os.path.isfile(binary):
            return {"analysis": analysis, "ran": False, "run": None}
        run = run_binary(binary, wd, stdin_text)
    return {"analysis": analysis, "ran": bool(run.get("started")), "run": run}


def _pick_fix_target(issues, skipped):
    from auto_healer import UNFIXABLE_CATEGORIES
    for kind in ("error", "warning"):
        for it in issues:
            if it.get("type") != kind or it.get("category") in UNFIXABLE_CATEGORIES:
                continue
            key = (it.get("line"), it.get("message"))
            if key in skipped:
                continue
            return it
    return None


def api_cpp_heal(body: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based or AI healing. Returns a PROPOSAL (original, patched, diff, steps)."""
    code = _need_code(body)
    mode = body.get("mode", "rules")
    if mode == "ai":
        return _heal_ai(code)
    if mode != "rules":
        raise ApiError("mode must be 'rules' or 'ai'.")

    from auto_healer import attempt_fix

    t0 = time.time()
    steps: List[Dict[str, Any]] = []
    current = code
    skipped: set = set()
    with tempfile.TemporaryDirectory(prefix="webui_") as wd:
        for attempt in range(1, HEAL_ATTEMPTS + 1):
            errors, _, _ = compile_cpp(current, wd)
            _classify(errors)
            target = _pick_fix_target(errors, skipped)
            if target is None:
                break
            patched = attempt_fix(current, target)
            if not patched or patched == current:
                skipped.add((target.get("line"), target.get("message")))
                steps.append({
                    "attempt": attempt, "fixed": False,
                    "line": target.get("line"), "message": target.get("message"),
                    "category": target.get("category"),
                    "note": "No automatic rule could fix this diagnostic.",
                })
                continue
            steps.append({
                "attempt": attempt, "fixed": True,
                "line": target.get("line"), "message": target.get("message"),
                "category": target.get("category"),
                "diff": diff_lines(current, patched, 1),
            })
            current = patched
        final_errors, _, src = compile_cpp(current, wd)
        _classify(final_errors)
        remaining = _enrich(final_errors, src)

    hard = sum(1 for e in remaining if e["type"] == "error")
    return {
        "mode": "rules",
        "original": code,
        "patched": current,
        "changed": current != code,
        "compiles": hard == 0,
        "steps": steps,
        "remaining": remaining,
        "diff": diff_lines(code, current, 3),
        "elapsed_s": round(time.time() - t0, 3),
    }


def _heal_ai(code: str) -> Dict[str, Any]:
    _require_llm()
    try:
        from agentic_compiler import CompilerAgent
    except Exception as exc:  # e.g. PyQt6 missing in the environment
        raise ApiError(f"AI agent could not be loaded: {exc}", 503)
    t0 = time.time()
    steps: List[Dict[str, Any]] = []

    def on_step(step, thought, action, meta):
        steps.append({"attempt": step, "thought": str(thought)[:600],
                      "action": str(action)[:200], "fixed": None})

    try:
        result = CompilerAgent().heal(code, None, on_step=on_step)
    except Exception as exc:
        raise ApiError(f"AI healing failed: {type(exc).__name__}: {exc}", 502)

    final = result.get("final_code") or code
    return {
        "mode": "ai",
        "original": code,
        "patched": final,
        "changed": final != code,
        "compiles": bool(result.get("success")),
        "steps": steps,
        "summary": result.get("summary", ""),
        "iterations": result.get("iterations"),
        "remaining": [],
        "diff": diff_lines(code, final, 3),
        "elapsed_s": round(time.time() - t0, 3),
    }


def api_cpp_ast(body: Dict[str, Any]) -> Dict[str, Any]:
    code = _need_code(body)
    from ast_extractor import extract_ast, parse_ast_to_tree
    if not shutil_which("clang++"):
        raise ApiError("clang++ was not found. Install clang to use the C++ AST view.", 503)
    with tempfile.TemporaryDirectory(prefix="webui_") as wd:
        src = os.path.join(wd, "main.cpp")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)
        text = extract_ast(src)
        tree = parse_ast_to_tree(text, src)
        # hide the temp directory in node details
        scrubbed = _scrub_paths(_to_jsonable(tree), wd)
    return {"tree": scrubbed, "node_count": _count_nodes(tree)}


def _scrub_paths(obj: Any, directory: str) -> Any:
    """Remove `directory` (and the separator after it) from every string in a JSON-like structure.

    Works on the data, not on JSON text, so Windows backslashes cannot corrupt the output.
    Matches both separator styles because clang may print either.
    """
    variants = {directory, directory.replace("\\", "/"), directory.replace("/", "\\")}
    prefixes = sorted({v + sep for v in variants for sep in ("\\", "/")}, key=len, reverse=True)

    def clean(value: Any) -> Any:
        if isinstance(value, str):
            for pre in prefixes:
                value = value.replace(pre, "")
            return value
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        return value

    return clean(obj)


def _count_nodes(tree: Any) -> int:
    if isinstance(tree, list):
        return sum(_count_nodes(t) for t in tree)
    if isinstance(tree, dict):
        return 1 + _count_nodes(tree.get("children", []))
    return 0


def shutil_which(name: str) -> Optional[str]:
    import shutil
    return shutil.which(name)


def gxx_available() -> bool:
    """Same lookup the compiler uses, so Windows installs outside PATH (MSYS2, MinGW, w64devkit) are found."""
    try:
        from compiler_runner import get_compiler_cmd_and_env
        import shutil
        gxx, env = get_compiler_cmd_and_env()
        return bool(shutil.which(gxx, path=env.get("PATH")) or os.path.isfile(gxx))
    except Exception:
        return bool(shutil_which("g++"))


# ──────────────────────────────────────────────────────────────────────────────
# MiniC pipeline
# ──────────────────────────────────────────────────────────────────────────────

def ast_to_json(node: Any) -> Any:
    """Generic AST -> {type, line, column, attrs, children:[{role, node}]} converter."""
    from core.ast_nodes import ASTNode
    if not isinstance(node, ASTNode):
        return None
    attrs: Dict[str, Any] = {}
    children: List[Dict[str, Any]] = []
    for f in dataclasses.fields(node):
        if f.name in ("line", "column"):
            continue
        val = getattr(node, f.name)
        if isinstance(val, ASTNode):
            children.append({"role": f.name, "node": ast_to_json(val)})
        elif isinstance(val, list) and val and all(isinstance(v, ASTNode) for v in val):
            for i, v in enumerate(val):
                children.append({"role": f"{f.name}[{i}]", "node": ast_to_json(v)})
        elif val is None:
            continue
        else:
            attrs[f.name] = val if isinstance(val, (str, int, float, bool)) else str(val)
    return {"type": type(node).__name__, "line": node.line, "column": node.column,
            "attrs": attrs, "children": children}


def _collect_locals(program: Any) -> List[Dict[str, Any]]:
    """Walk the AST and list every function, parameter and variable with its scope."""
    from core.ast_nodes import ASTNode, FunctionDef, VarDecl
    out: List[Dict[str, Any]] = []

    def walk(n: Any, scope: str) -> None:
        if isinstance(n, FunctionDef):
            out.append({"name": n.name, "kind": "function", "type": n.return_type,
                        "scope": "global", "line": n.line,
                        "detail": "(" + ", ".join(f"{t} {p}" for t, p in n.params) + ")"})
            for t, p in n.params:
                out.append({"name": p, "kind": "param", "type": t, "scope": n.name,
                            "line": n.line, "detail": ""})
            walk(n.body, n.name)
            return
        if isinstance(n, VarDecl):
            out.append({"name": n.name, "kind": "variable", "type": n.var_type,
                        "scope": scope, "line": n.line, "detail": ""})
        if isinstance(n, ASTNode):
            for f in dataclasses.fields(n):
                v = getattr(n, f.name)
                if isinstance(v, ASTNode):
                    walk(v, scope)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, ASTNode):
                            walk(item, scope)

    walk(program, "global")
    return out


def _inst_list(instructions: List[Any]) -> List[Dict[str, Any]]:
    return [{"i": i, "text": str(inst)} for i, inst in enumerate(instructions)]


def api_minic_pipeline(body: Dict[str, Any]) -> Dict[str, Any]:
    code = _need_code(body)
    from core.lexer import Lexer
    from core.parser import Parser
    from core.semantic import SemanticAnalyzer
    from core.ir import generate_ir
    from core.optimizer import optimize
    from core.interpreter import run_ir

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    lex_errors = [{"message": e.message, "line": e.line, "column": e.column} for e in lexer.errors]

    parser = Parser(tokens)
    program = parser.parse()
    parse_errors = [{"message": e.message, "line": e.line, "column": e.column,
                     "expected": getattr(e, "expected", None)} for e in parser.errors]

    result: Dict[str, Any] = {
        "tokens": [{"type": getattr(t.type, "name", str(t.type)), "lexeme": t.lexeme,
                    "line": t.line, "column": t.column} for t in tokens],
        "lex_errors": lex_errors,
        "parse_errors": parse_errors,
        "ast": ast_to_json(program),
        "semantic": [],
        "symbols": [],
        "ir": [], "optimized_ir": [], "opt_stats": {},
        "output": None, "optimized_output": None, "equivalent": None, "runtime_error": None,
        "stage_reached": "parse",
    }
    if lex_errors or parse_errors:
        return result

    analyzer = SemanticAnalyzer()
    diags = analyzer.analyze(program)
    result["semantic"] = [{"message": d.message, "line": d.line, "column": d.column,
                           "severity": d.severity} for d in diags]
    result["symbols"] = _collect_locals(program)
    result["stage_reached"] = "semantic"
    if any(d.severity == "error" for d in diags):
        return result

    try:
        ir = generate_ir(program)
        opt, stats = optimize(ir)
    except Exception as exc:
        result["runtime_error"] = f"IR generation failed: {type(exc).__name__}: {exc}"
        return result
    result["ir"] = _inst_list(ir)
    result["optimized_ir"] = _inst_list(opt)
    result["opt_stats"] = stats
    result["stage_reached"] = "ir"

    try:
        before = run_ir(ir)
        after = run_ir(opt)
        result.update(output=before, optimized_output=after, equivalent=(before == after))
        result["stage_reached"] = "executed"
    except Exception as exc:
        result["runtime_error"] = f"{type(exc).__name__}: {exc}"
    return result


def _ai_call(fn):
    """Run an AI function and translate known failures into friendly API errors."""
    _require_llm()
    try:
        return fn()
    except ApiError:
        raise
    except Exception as exc:
        name = type(exc).__name__
        if name == "GuardrailSecurityException":
            raise ApiError(f"Blocked by the AI security guardrail: {exc}", 403)
        if name == "LLMCommunicationError":
            raise ApiError(f"Could not reach the AI model: {exc}", 502)
        raise ApiError(f"AI feature failed: {name}: {exc}", 500)


def api_minic_ai(body: Dict[str, Any]) -> Dict[str, Any]:
    code = _need_code(body)
    action = body.get("action")
    if action not in ("explain", "optimize", "bugs"):
        raise ApiError("action must be one of: explain, optimize, bugs.")
    _require_llm()

    from core.lexer import Lexer
    from core.parser import Parser
    from core.semantic import SemanticAnalyzer

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    if lexer.errors or parser.errors:
        first = (lexer.errors or parser.errors)[0]
        raise ApiError(f"Fix syntax errors first (line {first.line}): {first.message}", 422)

    t0 = time.time()
    if action == "explain":
        from ai.phase_explainer import explain_compilation
        data = _ai_call(lambda: explain_compilation(code))
        return {"action": action, "result": _to_jsonable(data), "elapsed_s": round(time.time() - t0, 2)}

    if action == "bugs":
        from ai.bug_detector import detect_bugs
        data = _ai_call(lambda: detect_bugs(code, ast=program))
        return {"action": action, "result": _to_jsonable(data), "elapsed_s": round(time.time() - t0, 2)}

    # optimize
    from ai.ai_optimizer import ai_optimize_ir
    from core.ir import generate_ir
    analyzer = SemanticAnalyzer()
    diags = analyzer.analyze(program)
    if any(d.severity == "error" for d in diags):
        raise ApiError(f"Fix semantic errors first: {diags[0].message}", 422)
    ir = generate_ir(program)
    data = _ai_call(lambda: ai_optimize_ir(ir))
    before = [str(i) for i in data.get("initial_ir", ir)]
    after = [str(i) for i in data.get("optimized_ir", ir)]
    return {
        "action": action,
        "result": {
            "analysis": data.get("analysis", ""),
            "accepted": _to_jsonable(data.get("accepted_suggestions", [])),
            "rejected": _to_jsonable(data.get("rejected_suggestions", [])),
            "initial_count": data.get("initial_instruction_count", len(before)),
            "final_count": data.get("final_instruction_count", len(after)),
            "equivalence_verified": data.get("equivalence_verified"),
            "ir_before": before,
            "ir_after": after,
            "ir_diff": _text_diff(before, after),
        },
        "elapsed_s": round(time.time() - t0, 2),
    }


def _text_diff(a: List[str], b: List[str]) -> List[Dict[str, Any]]:
    return diff_lines("\n".join(a), "\n".join(b), 2)


# ──────────────────────────────────────────────────────────────────────────────
# Status, samples, benchmark
# ──────────────────────────────────────────────────────────────────────────────

MINIC_SAMPLES = [
    {"name": "Arithmetic & folding", "language": "minic", "code":
     "int main() {\n    int a = 10 * 5 + 20;\n    int b = a + 30;\n    print(b);\n    return b;\n}\n"},
    {"name": "Loop sum", "language": "minic", "code":
     "int main() {\n    int i = 0;\n    int total = 0;\n    while (i < 10) {\n        total = total + i * 2;\n        i = i + 1;\n    }\n    print(total);\n    return 0;\n}\n"},
    {"name": "Functions & recursion", "language": "minic", "code":
     "int fact(int n) {\n    if (n <= 1) {\n        return 1;\n    }\n    return n * fact(n - 1);\n}\n\nint main() {\n    print(fact(5));\n    return 0;\n}\n"},
    {"name": "Dead code", "language": "minic", "code":
     "int main() {\n    int x = 42;\n    int unused = 100 * 20;\n    int y = x + 0;\n    print(y);\n    return 0;\n}\n"},
    {"name": "Has semantic errors", "language": "minic", "code":
     "int main() {\n    int a = 1;\n    int a = 2;\n    b = 3;\n    bool flag = 5;\n    return 0;\n}\n"},
    {"name": "Has syntax errors", "language": "minic", "code":
     "int main() {\n    int x = ;\n    if (x > 0 {\n        print(x);\n    }\n    return 0;\n}\n"},
]

CPP_SAMPLE_FILES = [
    "mini/tc01_missing_semicolon.cpp", "mini/tc02_undeclared_variable.cpp",
    "mini/tc03_missing_include.cpp", "mini/tc05_missing_closing_brace.cpp",
    "mini/tc06_wrong_stream_operator.cpp", "mini/tc07_keyword_typo.cpp",
    "type_error.cpp", "success.cpp",
]


CPP_STARTERS = [
    {"name": "Hello, world", "language": "cpp", "code":
     '#include <iostream>\n\nint main() {\n    std::cout << "Hello, world!" << std::endl;\n    return 0;\n}\n'},
    {"name": "Add two numbers (reads input)", "language": "cpp", "code":
     '#include <iostream>\n\nint main() {\n    int a, b;\n    std::cout << "Enter two numbers: ";\n    std::cin >> a >> b;\n    std::cout << a << " + " << b << " = " << a + b << std::endl;\n    return 0;\n}\n'},
    {"name": "Fibonacci with a function", "language": "cpp", "code":
     '#include <iostream>\n\nint fib(int n) {\n    if (n < 2) return n;\n    return fib(n - 1) + fib(n - 2);\n}\n\nint main() {\n    for (int i = 0; i < 10; ++i) {\n        std::cout << fib(i) << " ";\n    }\n    std::cout << std::endl;\n    return 0;\n}\n'},
]


def api_samples() -> Dict[str, Any]:
    samples = list(MINIC_SAMPLES) + [dict(x) for x in CPP_STARTERS]
    for rel in CPP_SAMPLE_FILES:
        p = ROOT_DIR / "test_cases" / rel
        if p.is_file() and p.stat().st_size < 20_000:
            nice = p.stem.replace("_", " ")
            samples.append({"name": nice, "language": "cpp",
                            "code": p.read_text(encoding="utf-8", errors="replace")})
    return {"samples": samples}


def api_status() -> Dict[str, Any]:
    model = None
    try:
        from ai.llm_client import DEFAULT_MODEL
        model = DEFAULT_MODEL
    except Exception:
        pass
    return {
        "llm_key_present": bool(_api_key()),
        "llm_mock": _mock_enabled(),
        "ai_ready": bool(_api_key()) or _mock_enabled(),
        "model": model,
        "gxx": gxx_available(),
        "clang": bool(shutil_which("clang++")),
        "heal_attempts": HEAL_ATTEMPTS,
    }


def _num(row: Dict[str, str], key: str) -> Optional[float]:
    try:
        return float(row.get(key, ""))
    except (TypeError, ValueError):
        return None


def api_benchmark() -> Dict[str, Any]:
    """Read results/final.csv and recompute every aggregate from the raw rows."""
    path = ROOT_DIR / "results" / "final.csv"
    if not path.is_file():
        raise ApiError("results/final.csv not found. Run src/evaluation/benchmark.py first.", 404)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    healing = [r for r in rows if r.get("suite") == "healing"]
    broken = [r for r in healing if str(r.get("baseline_clean", "")).lower() != "true"]
    rule_ok = [r for r in broken if r.get("rule_compiled") == "yes"]
    ai_ok = [r for r in broken if r.get("llm_compiled") == "yes"]
    ai_ran = [r for r in broken if r.get("llm_compiled") in ("yes", "no")]
    clf_ok = [r for r in healing if r.get("category_matched") == "yes"]

    def avg(rs, key):
        vals = [v for v in (_num(r, key) for r in rs) if v is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    def pct(a, b):
        return round(100.0 * a / b, 1) if b else None

    verifier = [r for r in rows if r.get("suite") == "ai_optimizer"]
    live = [r for r in rows if r.get("suite") == "live_llm_optimizer"]

    def sums(rs, k):
        return int(sum(_num(r, k) or 0 for r in rs))

    return {
        "healing": {
            "total_fixtures": len(healing),
            "already_clean": len(healing) - len(broken),
            "broken": len(broken),
            "rule_fixed": len(rule_ok),
            "rule_rate": pct(len(rule_ok), len(broken)),
            "rule_avg_s": avg(broken, "rule_time_sec"),
            "ai_ran": len(ai_ran),
            "ai_fixed": len(ai_ok),
            "ai_rate": pct(len(ai_ok), len(ai_ran)) if ai_ran else None,
            "ai_avg_s": avg(ai_ran, "llm_time_sec"),
            # AI "misses" that returned in <50 ms never reached the model: the
            # security guardrail blocked those (attack-test) files on purpose.
            "ai_guardrail_blocked": sum(
                1 for r in ai_ran
                if r.get("llm_compiled") == "no" and (_num(r, "llm_time_sec") or 0) < 0.05
            ),
            "classifier_accuracy": pct(len(clf_ok), len(healing)),
            "note": "'Fixed' means the file now compiles; it does not prove the program still behaves correctly.",
        },
        "verifier": {
            "programs": len(verifier),
            "proposed": sums(verifier, "suggestions_proposed"),
            "accepted": sums(verifier, "suggestions_accepted"),
            "rejected": sums(verifier, "suggestions_rejected"),
            "note": "Scripted test of the equivalence checker with hand-written good and bad suggestions. Not an AI result.",
        },
        "live_optimizer": {
            "programs": len(live),
            "proposed": sums(live, "suggestions_proposed"),
            "accepted": sums(live, "suggestions_accepted"),
            "rejected": sums(live, "suggestions_rejected"),
            "ir_removed": sums(live, "instruction_delta") * -1,
            "note": "Real Gemini suggestions on MiniC programs, accepted only if program output is unchanged.",
        },
        "per_file": [
            {"file": os.path.basename(r.get("file", "")),
             "baseline_clean": str(r.get("baseline_clean", "")).lower() == "true",
             "rule": r.get("rule_compiled"), "ai": r.get("llm_compiled"),
             "rule_time": _num(r, "rule_time_sec"), "ai_time": _num(r, "llm_time_sec")}
            for r in healing
        ],
        "live_rows": [
            {"file": r.get("file"), "proposed": _num(r, "suggestions_proposed"),
             "accepted": _num(r, "suggestions_accepted"), "rejected": _num(r, "suggestions_rejected"),
             "initial": _num(r, "initial_instructions"), "final": _num(r, "final_instructions")}
            for r in live
        ],
        "verifier_rows": [
            {"file": r.get("file"), "proposed": _num(r, "suggestions_proposed"),
             "accepted": _num(r, "suggestions_accepted"), "rejected": _num(r, "suggestions_rejected"),
             "reason": r.get("rejection_reasons")}
            for r in verifier
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# HTTP layer
# ──────────────────────────────────────────────────────────────────────────────

POST_ROUTES = {
    "/api/cpp/analyze": api_cpp_analyze,
    "/api/cpp/run": api_cpp_run,
    "/api/cpp/heal": api_cpp_heal,
    "/api/cpp/ast": api_cpp_ast,
    "/api/minic/pipeline": api_minic_pipeline,
    "/api/minic/ai": api_minic_ai,
}
GET_ROUTES = {
    "/api/status": api_status,
    "/api/samples": api_samples,
    "/api/benchmark": api_benchmark,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "GreenCompilerUI/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("WEBUI_VERBOSE"):
            super().log_message(fmt, *args)

    # -- responses ------------------------------------------------------------
    def _send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_static(self, rel: str) -> None:
        rel = rel.lstrip("/") or "index.html"
        target = (STATIC_DIR / rel).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            return self._send_json({"error": "Not found"}, 404)
        if not target.is_file():
            return self._send_json({"error": "Not found"}, 404)
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8" if ctype.startswith("text/") or "javascript" in ctype else ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # -- verbs ----------------------------------------------------------------
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        fn = GET_ROUTES.get(path)
        if fn:
            return self._run(fn)
        if path.startswith("/api/"):
            return self._send_json({"error": "Unknown endpoint"}, 404)
        self._send_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        fn = POST_ROUTES.get(path)
        if not fn:
            return self._send_json({"error": "Unknown endpoint"}, 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            return self._send_json({"error": "Request body missing or too large."}, 413 if length else 400)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            return self._send_json({"error": "Request body must be a JSON object."}, 400)
        self._run(fn, body)

    def _run(self, fn, *args) -> None:
        try:
            self._send_json(fn(*args))
        except ApiError as e:
            self._send_json({"error": e.message}, e.status)
        except Exception as e:  # last-resort guard so the UI always gets JSON
            if os.environ.get("WEBUI_VERBOSE"):
                traceback.print_exc()
            self._send_json({"error": f"Internal error: {type(e).__name__}: {e}"}, 500)


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    _load_env()
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv


def main() -> int:
    ap = argparse.ArgumentParser(description="Green Self-Healing Compiler web UI")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    srv = make_server(args.host, args.port)
    url = f"http://{args.host}:{args.port}/"
    st = api_status()
    print(f"Green Self-Healing Compiler web UI running at {url}")
    print(f"  g++: {'yes' if st['gxx'] else 'NO'} | clang++: {'yes' if st['clang'] else 'no'} | "
          f"AI: {'ready' if st['ai_ready'] else 'no API key (set GEMINI_API_KEY)'}"
          f"{' [MOCK MODE]' if st['llm_mock'] else ''}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
