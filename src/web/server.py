"""
server.py
---------
Local web UI for the Green Self-Healing Compiler.

Runs on Python's standard library only (no Flask/FastAPI needed) and reuses the
existing modules: error_explainer, auto_healer, diff_viewer, ast_extractor,
security_analyzer, and agentic_compiler.

Usage:
    python src/web/server.py                # http://127.0.0.1:8765
    python src/web/server.py --port 9000 --no-browser

Safety notes:
  * Binds to 127.0.0.1 only (never exposed to the network by default).
  * Request bodies are capped; compiler runs have timeouts and use temp dirs.
  * "Run" compiles the C++ and executes it on THIS machine, like any IDE. It is only
    enabled while the server is bound to localhost, never for code the existing
    security check blocks, and the program gets a temp working directory, a 5 s
    timeout, a 64 KB output cap and (on Linux/macOS) CPU/memory/file-size limits.
    It is not a sandbox: only run code you trust.
  * Healing endpoints only PROPOSE a patch. The browser shows the diff and the
    user accepts or rejects it; nothing is written to disk by the server.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import mimetypes
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
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
from urllib.parse import parse_qs, urlparse

WEB_DIR = Path(__file__).resolve().parent
SRC_DIR = WEB_DIR.parent
ROOT_DIR = SRC_DIR.parent
STATIC_DIR = WEB_DIR / "static"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from languages import Language, NotSupported, ToolchainNotFound, get_language, list_languages
from languages.cpp import CppLanguage, OUT_NAME, _ERR_PATTERN
from energy_meter import build_energy_object, compute_estimated_energy_joules, get_cpu_watts

try:
    from aai_guardrail import AAIGuardrail, normalize, verify_log, GuardrailResult
except Exception:
    AAIGuardrail = None
    normalize = None
    verify_log = None
    GuardrailResult = None

MAX_BODY_BYTES = 1_000_000
COMPILE_TIMEOUT_S = 30
HEAL_ATTEMPTS = 10
RUN_TIMEOUT_S = 5            # a program that runs longer than this is stopped
RUN_OUTPUT_CAP = 64 * 1024   # bytes of stdout/stderr kept; more than this stops the program
RUN_STDIN_CAP = 64 * 1024
OUT_NAME = "out.exe" if os.name == "nt" else "out.bin"
# Running compiled programs is only allowed while the server listens on this machine only.
# make_server() switches this off for any non-loopback host.
RUN_ENABLED = True

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


def _get_lang(body: Dict[str, Any]) -> Language:
    lang_id = body.get('language', 'cpp')
    if not isinstance(lang_id, str) or not lang_id.strip():
        lang_id = 'cpp'
    lang = get_language(lang_id)
    if not lang:
        raise ApiError(f"Unsupported language: '{lang_id}'", 400)
    return lang


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
    lang = get_language("cpp")
    if not lang:
        raise ApiError("C++ language driver not available.", 500)
    try:
        errors = lang.check(code, workdir)
    except ToolchainNotFound as e:
        raise ApiError(str(e), 503)
    except FileNotFoundError:
        raise ApiError("g++ was not found on this machine. Install a C++ toolchain and restart.", 503)
    stderr = getattr(lang, "last_stderr", "")
    src = os.path.join(workdir, "main.cpp")
    return errors, stderr, src


def _run_binary(exe: str, workdir: str, stdin_text: str, env: Dict[str, str]) -> Dict[str, Any]:
    """Run a compiled program with a timeout, an output cap and (on POSIX) resource limits."""
    lang = get_language("cpp")
    if isinstance(lang, CppLanguage):
        return lang._run_binary(exe, workdir, stdin_text, env, timeout=RUN_TIMEOUT_S)
    return CppLanguage()._run_binary(exe, workdir, stdin_text, env, timeout=RUN_TIMEOUT_S)


def api_cpp_compile(body: Dict[str, Any]) -> Dict[str, Any]:
    """Compile only (no explanations): the quick 'does it build?' action."""
    return api_cpp_analyze(body)


def api_cpp_run(body: Dict[str, Any]) -> Dict[str, Any]:
    """Compile and run. Never runs anything if the compile fails or the code is blocked."""
    if not RUN_ENABLED:
        raise ApiError("Running programs is disabled because the server is not bound to this machine only.", 403)
    code = _need_code(body)
    lang = _get_lang(body)
    stdin_text = body.get("stdin", "")
    if not isinstance(stdin_text, str) or len(stdin_text) > RUN_STDIN_CAP:
        raise ApiError("stdin must be text of at most 64 KB.")
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="webui_") as wd:
        try:
            errors = lang.check(code, wd)
        except ToolchainNotFound as e:
            raise ApiError(str(e), 503)
        except FileNotFoundError:
            raise ApiError(f"{lang.name} compiler was not found on this machine. Install toolchain and restart.", 503)
        stderr = getattr(lang, "last_stderr", "")
        ext = lang.extensions[0] if lang.extensions else ".cpp"
        src = os.path.join(wd, f"main{ext}")
        _classify(errors)
        enriched = _enrich(errors, src)
        security = _security_findings(src)
        hard = sum(1 for e in enriched if e["type"] == "error")
        warn = sum(1 for e in enriched if e["type"] == "warning")
        result: Dict[str, Any] = {
            "ok": hard == 0,
            "error_count": hard,
            "warning_count": warn,
            "diagnostics": enriched,
            "security": security,
            "raw_stderr": stderr.strip(),
            "ran": False,
        }
        if hard == 0:
            run_data = lang.run(code, wd, stdin=stdin_text, timeout=RUN_TIMEOUT_S)
            result.update(run_data)
            result["ran"] = True

    elapsed_s = round(time.time() - t0, 3)
    result["elapsed_s"] = elapsed_s

    analysis = {
        "ok": result["ok"],
        "error_count": result["error_count"],
        "warning_count": result["warning_count"],
        "diagnostics": result["diagnostics"],
        "security": result.get("security", []),
        "raw_stderr": result["raw_stderr"],
        "elapsed_s": elapsed_s,
    }
    result["analysis"] = analysis

    if result["ran"]:
        energy_obj = build_energy_object(result, getattr(lang, "last_compile_metrics", None))
        result["energy"] = energy_obj
        run_obj = {
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", 0),
            "timed_out": bool(result.get("timed_out")),
            "output_flood": bool(result.get("output_flood")),
            "truncated": bool(result.get("truncated")),
            "signal": result.get("signal"),
            "signal_hint": result.get("signal_hint"),
            "timeout_s": RUN_TIMEOUT_S,
            "elapsed_ms": int(result.get("run_s", elapsed_s) * 1000) if "run_s" in result else int(elapsed_s * 1000),
            "elapsed_s": result.get("run_s", elapsed_s),
            "energy": energy_obj,
        }
        result["run"] = run_obj
        result["elapsed_ms"] = run_obj["elapsed_ms"]
        result["truncated"] = run_obj["truncated"]
    else:
        result["run"] = None
        result["energy"] = None

    return result


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


def api_cpp_analyze(body: Dict[str, Any]) -> Dict[str, Any]:
    code = _need_code(body)
    lang = _get_lang(body)
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="webui_") as wd:
        try:
            errors = lang.check(code, wd)
        except ToolchainNotFound as e:
            raise ApiError(str(e), 503)
        except FileNotFoundError:
            raise ApiError(f"{lang.name} compiler was not found on this machine. Install toolchain and restart.", 503)
        stderr = getattr(lang, "last_stderr", "")
        ext = lang.extensions[0] if lang.extensions else ".cpp"
        src = os.path.join(wd, f"main{ext}")
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


def _pick_independent_fix_targets(issues, skipped):
    from auto_healer import UNFIXABLE_CATEGORIES
    targets = []
    seen_lines = set()
    has_header = False
    for kind in ("error", "warning"):
        for it in issues:
            if it.get("type") != kind or it.get("category") in UNFIXABLE_CATEGORIES:
                continue
            key = (it.get("line"), it.get("message"))
            if key in skipped:
                continue
            line = it.get("line")
            cat = it.get("category")
            if cat == "missing_include":
                if not has_header:
                    targets.append(it)
                    has_header = True
            elif line is not None and line > 0:
                if line not in seen_lines:
                    seen_lines.add(line)
                    targets.append(it)
            elif not targets:
                targets.append(it)
    return targets


def api_cpp_heal(body: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based or AI healing. Returns a PROPOSAL (original, patched, diff, steps)."""
    code = _need_code(body)
    lang = _get_lang(body)
    mode = body.get("mode", "rules")
    if mode == "ai":
        return _heal_ai(code, language=lang.id)
    if mode != "rules":
        raise ApiError("mode must be 'rules' or 'ai'.")

    from auto_healer import attempt_fix

    t0 = time.time()
    steps: List[Dict[str, Any]] = []
    current = code
    skipped: set = set()
    ext = lang.extensions[0] if lang.extensions else ".cpp"
    prev_error_count = float("inf")

    with tempfile.TemporaryDirectory(prefix="webui_") as wd:
        for attempt in range(1, HEAL_ATTEMPTS + 1):
            try:
                errors = lang.check(current, wd)
            except ToolchainNotFound as e:
                raise ApiError(str(e), 503)
            except FileNotFoundError:
                raise ApiError(f"{lang.name} compiler was not found on this machine.", 503)

            hard_errors = [e for e in errors if e.get("type") == "error"]
            if not hard_errors:
                break

            # Stop early when the error set stops shrinking
            if attempt > 1 and len(hard_errors) >= prev_error_count:
                break
            prev_error_count = len(hard_errors)

            _classify(errors)
            targets = _pick_independent_fix_targets(errors, skipped)
            if not targets:
                break

            line_targets = [t for t in targets if t.get("category") != "missing_include" and (t.get("line") or 0) > 0]
            line_targets.sort(key=lambda t: t.get("line", 0), reverse=True)
            other_targets = [t for t in targets if t not in line_targets]

            applied_any = False
            for target in line_targets + other_targets:
                if lang.id == "python":
                    from languages.python_rules import attempt_fix_python
                    patched = attempt_fix_python(current, target)
                elif lang.id == "java":
                    from languages.java_rules import attempt_fix_java
                    patched = attempt_fix_java(current, target)
                else:
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

                applied_any = True
                steps.append({
                    "attempt": attempt, "fixed": True,
                    "line": target.get("line"), "message": target.get("message"),
                    "category": target.get("category"),
                    "diff": diff_lines(current, patched, 1),
                })
                current = patched

            if not applied_any:
                break

        final_errors = lang.check(current, wd)
        _classify(final_errors)
        src = os.path.join(wd, f"main{ext}")
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


def _heal_ai(code: str, language: str = "cpp") -> Dict[str, Any]:
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
        result = CompilerAgent(language=language).heal(code, None, on_step=on_step, language=language)
    except Exception as exc:
        raise ApiError(f"AI healing failed: {type(exc).__name__}: {exc}", 502)

    final = result.get("final_code") or code
    finding = result.get("guardrail_finding") or {}
    attack_blocked = bool(result.get("attack_blocked"))
    review_required = bool(result.get("review_required"))
    risk_level = finding.get("risk_level") or ("CRITICAL" if attack_blocked else ("MEDIUM" if review_required else "LOW"))
    risk_score = finding.get("risk_score", 0.0)
    reason = finding.get("description") or result.get("warning") or result.get("summary", "")
    action_taken = finding.get("action_taken") or ("Discarded malicious patch" if attack_blocked else ("Flagged for human review" if review_required else "Allowed"))
    evidence = result.get("evidence") or finding.get("evidence") or []

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
        "attack_blocked": attack_blocked,
        "review_required": review_required,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "reason": reason,
        "action_taken": action_taken,
        "evidence": _to_jsonable(evidence),
        "guardrail_finding": _to_jsonable(finding),
    }


def api_cpp_ast(body: Dict[str, Any]) -> Dict[str, Any]:
    code = _need_code(body)
    lang = _get_lang(body)
    try:
        scrubbed = lang.tree(code)
    except NotSupported as exc:
        raise ApiError(str(exc), 503)
    except Exception as exc:
        raise ApiError(f"AST extraction failed: {exc}", 500)
    return {"tree": scrubbed, "node_count": _count_nodes(scrubbed)}


def _scrub_paths(obj: Any, prefixes: List[str]) -> Any:
    """Remove the temp directory from every string in a JSON-like structure (works for Windows paths too)."""
    if isinstance(obj, str):
        for pre in prefixes:
            obj = obj.replace(pre, "")
        return obj
    if isinstance(obj, list):
        return [_scrub_paths(x, prefixes) for x in obj]
    if isinstance(obj, dict):
        return {k: _scrub_paths(v, prefixes) for k, v in obj.items()}
    return obj


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
    lang = get_language("cpp")
    if lang:
        return lang.toolchain_available()
    try:
        from compiler_runner import get_compiler_cmd_and_env
        import shutil
        gxx, env = get_compiler_cmd_and_env()
        return bool(shutil.which(gxx, path=env.get("PATH")) or os.path.isfile(gxx))
    except Exception:
        return bool(shutil_which("g++"))


# ──────────────────────────────────────────────────────────────────────────────
# Status, samples, benchmark
# ──────────────────────────────────────────────────────────────────────────────

CPP_SAMPLE_FILES = [
    "mini/tc01_missing_semicolon.cpp", "mini/tc02_undeclared_variable.cpp",
    "mini/tc03_missing_include.cpp", "mini/tc05_missing_closing_brace.cpp",
    "mini/tc06_wrong_stream_operator.cpp", "mini/tc07_keyword_typo.cpp",
    "type_error.cpp", "success.cpp",
]


def api_samples(language: str = "cpp") -> Dict[str, Any]:
    lang_id = (language or "cpp").lower().strip()
    samples: List[Dict[str, Any]] = []
    lang_dir = ROOT_DIR / "test_cases" / lang_id
    if lang_dir.is_dir():
        for p in sorted(lang_dir.iterdir()):
            if p.is_file() and p.stat().st_size < 20_000 and not p.name.startswith("."):
                nice = p.stem.replace("_", " ")
                samples.append({
                    "name": nice,
                    "filename": p.name,
                    "language": lang_id,
                    "code": p.read_text(encoding="utf-8", errors="replace"),
                })
    if not samples and lang_id == "cpp":
        for rel in CPP_SAMPLE_FILES:
            p = ROOT_DIR / "test_cases" / rel
            if p.is_file() and p.stat().st_size < 20_000:
                nice = p.stem.replace("_", " ")
                samples.append({
                    "name": nice,
                    "filename": p.name,
                    "language": "cpp",
                    "code": p.read_text(encoding="utf-8", errors="replace"),
                })
    return {"samples": samples, "language": lang_id}


def api_status() -> Dict[str, Any]:
    model = None
    try:
        from ai.llm_client import DEFAULT_MODEL
        model = DEFAULT_MODEL
    except Exception:
        pass
    languages_info = [
        {"id": l.id, "name": l.name, "available": l.toolchain_available()}
        for l in list_languages()
    ]
    return {
        "llm_key_present": bool(_api_key()),
        "llm_mock": _mock_enabled(),
        "ai_ready": bool(_api_key()) or _mock_enabled(),
        "model": model,
        "gxx": gxx_available(),
        "clang": bool(shutil_which("clang++")),
        "heal_attempts": HEAL_ATTEMPTS,
        "run_enabled": RUN_ENABLED,
        "run_timeout_s": RUN_TIMEOUT_S,
        "languages": languages_info,
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

    # Multi-language breakdown
    by_lang: Dict[str, Any] = {}
    for lid in ("cpp", "c", "python", "java"):
        l_rows = [r for r in healing if r.get("language") == lid]
        if not l_rows:
            continue
        l_broken = [r for r in l_rows if str(r.get("baseline_clean", "")).lower() != "true"]
        l_rule_ok = [r for r in l_broken if r.get("rule_compiled") == "yes"]
        l_ai_ok = [r for r in l_broken if r.get("llm_compiled") == "yes"]
        l_ai_ran = [r for r in l_broken if r.get("llm_compiled") in ("yes", "no")]
        l_clf_ok = [r for r in l_rows if r.get("category_matched") == "yes"]
        has_rules = any(r.get("rule_compiled") != "n/a" for r in l_broken)
        by_lang[lid] = {
            "language": lid,
            "name": {"cpp": "C++", "c": "C", "python": "Python", "java": "Java"}.get(lid, lid.upper()),
            "total_fixtures": len(l_rows),
            "already_clean": len(l_rows) - len(l_broken),
            "broken": len(l_broken),
            "classification_technique": "ML (Scikit-Learn TF-IDF)" if lid in ("cpp", "c") else "Deterministic Keywords",
            "healing_pipeline": "Rule-Based + Gemini Agent" if lid in ("cpp", "c") else "Gemini Agent Only",
            "has_rules": has_rules,
            "rule_fixed": len(l_rule_ok) if has_rules else 0,
            "rule_rate": pct(len(l_rule_ok), len(l_broken)) if has_rules else None,
            "rule_avg_s": avg(l_broken, "rule_time_sec") if has_rules else None,
            "ai_ran": len(l_ai_ran),
            "ai_fixed": len(l_ai_ok),
            "ai_rate": pct(len(l_ai_ok), len(l_ai_ran)) if l_ai_ran else None,
            "ai_avg_s": avg(l_ai_ran, "llm_time_sec"),
            "classifier_accuracy": pct(len(l_clf_ok), len(l_rows)),
        }

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
            "ai_guardrail_blocked": sum(
                1 for r in ai_ran
                if r.get("llm_compiled") == "no" and (_num(r, "llm_time_sec") or 0) < 0.05
            ),
            "classifier_accuracy": pct(len(clf_ok), len(healing)),
            "note": "'Fixed' means the file now compiles; it does not prove the program still behaves correctly.",
        },
        "by_language": by_lang,
        "per_file": [
            {"file": os.path.basename(r.get("file", "")),
             "language": r.get("language", "cpp"),
             "baseline_clean": str(r.get("baseline_clean", "")).lower() == "true",
             "rule": r.get("rule_compiled"), "ai": r.get("llm_compiled"),
             "rule_time": _num(r, "rule_time_sec"), "ai_time": _num(r, "llm_time_sec")}
            for r in healing
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# AAI Security Endpoints (Attack Lab, Audit Log, Metrics)
# ──────────────────────────────────────────────────────────────────────────────

AUDIT_LOG_PATH = ROOT_DIR / "logs" / "aai_audit.jsonl"


def get_audit_log_path() -> Path:
    env_path = os.environ.get("AAI_AUDIT_LOG_PATH")
    if env_path:
        return Path(env_path)
    return AUDIT_LOG_PATH


def set_audit_log_path(path: Optional[Any]) -> None:
    global AUDIT_LOG_PATH, _guardrail_instance
    if path is None:
        AUDIT_LOG_PATH = ROOT_DIR / "logs" / "aai_audit.jsonl"
    else:
        AUDIT_LOG_PATH = Path(path)
    with _guardrail_lock:
        _guardrail_instance = None


_guardrail_lock = threading.Lock()
_guardrail_instance = None


def _get_guardrail():
    global _guardrail_instance
    with _guardrail_lock:
        if _guardrail_instance is None and AAIGuardrail is not None:
            _guardrail_instance = AAIGuardrail(audit_log_path=str(get_audit_log_path()))
        return _guardrail_instance


def api_aai_scan(body: Dict[str, Any]) -> Dict[str, Any]:
    stage = str(body.get("stage", "ingress")).lower().strip()
    input_text = body.get("input", "")
    if not isinstance(input_text, str):
        input_text = str(input_text)
    language = str(body.get("language", "cpp")).lower().strip()
    original_code = body.get("original_code", "")
    if not isinstance(original_code, str):
        original_code = str(original_code)
    enable_guardrails = bool(body.get("enable_guardrails", True))

    t0 = time.time()
    norm_text = normalize(input_text) if normalize is not None else input_text

    if not enable_guardrails:
        return {
            "ok": True,
            "decision": "ALLOW",
            "risk_score": 0.0,
            "risk_level": "LOW",
            "confidence": 1.0,
            "categories": [],
            "action_taken": "Demo Mode: Guardrails disabled. Request allowed unconditionally without inspection.",
            "evidence": [],
            "attack_type": None,
            "trigger_pattern": None,
            "normalized_text": norm_text,
            "guardrail_enabled": False,
            "latency_ms": round((time.time() - t0) * 1000, 2),
            "stage": stage,
            "language": language,
        }

    gr = _get_guardrail()
    if gr is None:
        raise ApiError("AAI Guardrail engine is not available.", 500)

    if stage == "egress":
        res = gr.scan_egress(original_code, input_text, language=language)
    else:
        res = gr.scan_ingress(input_text)

    return {
        "ok": True,
        "decision": res.decision,
        "risk_score": round(float(res.risk_score), 1),
        "risk_level": res.risk_level,
        "confidence": round(float(getattr(res, "confidence", 1.0)), 3),
        "categories": list(getattr(res, "categories", [])),
        "action_taken": res.action_taken,
        "evidence": _to_jsonable(getattr(res, "evidence", [])),
        "attack_type": getattr(res, "attack_type", None),
        "trigger_pattern": getattr(res, "trigger_pattern", None),
        "normalized_text": norm_text,
        "guardrail_enabled": True,
        "latency_ms": round((time.time() - t0) * 1000, 2),
        "stage": stage,
        "language": language,
    }


def api_aai_samples() -> Dict[str, Any]:
    samples: List[Dict[str, Any]] = []
    atk_path = ROOT_DIR / "data" / "aai" / "attacks.jsonl"
    if atk_path.is_file():
        with open(atk_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        samples.append(json.loads(line))
                    except Exception:
                        pass
    ben_path = ROOT_DIR / "data" / "aai" / "benign.jsonl"
    if ben_path.is_file():
        with open(ben_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        samples.append(json.loads(line))
                    except Exception:
                        pass
    return {"samples": samples, "total": len(samples)}


def api_aai_log(limit: int = 500) -> Dict[str, Any]:
    log_file = get_audit_log_path()
    if not log_file.is_file():
        return {
            "records": [],
            "total": 0,
            "summary": {"total": 0, "blocked": 0, "review": 0, "allowed": 0, "critical": 0, "high": 0, "by_class": {}, "by_stage": {}},
        }
    records: List[Dict[str, Any]] = []
    total = 0
    blocked = 0
    review = 0
    allowed = 0
    critical = 0
    high = 0
    by_class: Dict[str, int] = {}
    by_stage: Dict[str, int] = {}

    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            total += 1
            dec = str(rec.get("decision", "")).upper()
            if dec == "BLOCK":
                blocked += 1
            elif dec == "REVIEW":
                review += 1
            elif dec == "ALLOW":
                allowed += 1

            lvl = str(rec.get("risk_level", "")).upper()
            if lvl == "CRITICAL":
                critical += 1
            elif lvl == "HIGH":
                high += 1

            cls_name = rec.get("class") or "Other"
            by_class[cls_name] = by_class.get(cls_name, 0) + 1

            stg = rec.get("stage") or "ingress"
            by_stage[stg] = by_stage.get(stg, 0) + 1

            records.append(rec)

    records.reverse()
    capped = records[:limit] if limit > 0 else records
    return {
        "records": capped,
        "total": total,
        "summary": {
            "total": total,
            "blocked": blocked,
            "review": review,
            "allowed": allowed,
            "critical": critical,
            "high": high,
            "by_class": by_class,
            "by_stage": by_stage,
        },
    }


def api_aai_verify_log() -> Dict[str, Any]:
    if verify_log is None:
        raise ApiError("AAI Guardrail verify_log is not available.", 500)
    log_path = get_audit_log_path()
    res = verify_log(str(log_path))
    return {
        "ok": True,
        "valid": bool(res.valid),
        "total_records": res.total_records,
        "verified_records": res.get("verified_records", 0),
        "broken_record": _to_jsonable(res.broken_record) if res.broken_record else None,
        "broken_line": res.broken_line,
        "error": res.error,
        "reason": res.get("reason"),
    }


def api_aai_metrics() -> Dict[str, Any]:
    metrics_path = ROOT_DIR / "results" / "aai_metrics.json"
    if not metrics_path.is_file():
        raise ApiError("results/aai_metrics.json not found.", 404)
    with open(metrics_path, encoding="utf-8") as f:
        return json.load(f)


def api_energy_compare(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build C or C++ code with -O0 and -O2, run each 3 times with the same stdin (5 s limit),
    and return median wall time, CPU time, estimated energy, and savings.
    Flags undefined behaviour if -O0 and -O2 outputs differ.
    """
    if not RUN_ENABLED:
        raise ApiError("Running programs is disabled because the server is not bound to this machine only.", 403)

    code = _need_code(body)
    lang_name = body.get("language") or body.get("lang") or "cpp"
    lang_id = str(lang_name).lower().strip()
    if lang_id not in ("cpp", "c"):
        raise ApiError("Optimization comparison (-O0 vs -O2) is only available for C and C++.", 400)

    lang = get_language(lang_id)
    if not lang or not lang.toolchain_available():
        raise ApiError(f"{lang_id.upper()} compiler toolchain was not found on this machine.", 503)

    safe, reason = lang.is_safe(code)
    if not safe:
        raise ApiError(f"Security Error: {reason}", 400)

    stdin_text = body.get("stdin", "")
    if not isinstance(stdin_text, str) or len(stdin_text) > RUN_STDIN_CAP:
        raise ApiError("stdin must be text of at most 64 KB.", 400)

    import statistics
    from compiler_runner import get_compiler_cmd_and_env
    from languages.c import _find_gcc

    if lang_id == "cpp":
        compiler_cmd, env = get_compiler_cmd_and_env()
        base_args = [compiler_cmd, "-std=c++17", "-Wall"]
        ext = ".cpp"
    else:
        compiler_cmd, env = _find_gcc()
        base_args = [compiler_cmd, "-std=c11", "-Wall", "-Werror=implicit-function-declaration"]
        ext = ".c"

    env = {**env, "LC_ALL": "C", "LANGUAGE": "C"}
    cpu_watts = get_cpu_watts()

    with tempfile.TemporaryDirectory(prefix="energy_cmp_", ignore_cleanup_errors=True) as wd:
        src = os.path.join(wd, f"main{ext}")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)

        exe_o0 = os.path.join(wd, "out_o0.exe" if os.name == "nt" else "out_o0.bin")
        exe_o2 = os.path.join(wd, "out_o2.exe" if os.name == "nt" else "out_o2.bin")

        # 1. Compile -O0
        cmd_o0 = base_args + ["-O0", src, "-o", exe_o0]
        res_o0 = subprocess.run(cmd_o0, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=wd, env=env, timeout=COMPILE_TIMEOUT_S)
        if res_o0.returncode != 0:
            raise ApiError(f"Compilation with -O0 failed:\n{res_o0.stderr.strip()}", 400)

        # 2. Compile -O2
        cmd_o2 = base_args + ["-O2", src, "-o", exe_o2]
        res_o2 = subprocess.run(cmd_o2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=wd, env=env, timeout=COMPILE_TIMEOUT_S)
        if res_o2.returncode != 0:
            raise ApiError(f"Compilation with -O2 failed:\n{res_o2.stderr.strip()}", 400)

        # 3. Run -O0 3 times
        runs_o0 = []
        for _ in range(3):
            r = lang._run_binary(exe_o0, wd, stdin_text, env, timeout=RUN_TIMEOUT_S)
            wall = float(r.get("wall_s") if r.get("wall_s") is not None else r.get("run_s", 0.0))
            cpu = float(r.get("cpu_s") if r.get("cpu_s") is not None else 0.0)
            energy_j = compute_estimated_energy_joules(cpu, cpu_watts) or 0.0
            runs_o0.append({
                "wall_s": wall,
                "cpu_s": cpu,
                "est_energy_j": energy_j,
                "stdout": r.get("stdout", ""),
                "stderr": r.get("stderr", ""),
                "exit_code": r.get("exit_code", 0),
                "timed_out": bool(r.get("timed_out")),
            })

        # 4. Run -O2 3 times
        runs_o2 = []
        for _ in range(3):
            r = lang._run_binary(exe_o2, wd, stdin_text, env, timeout=RUN_TIMEOUT_S)
            wall = float(r.get("wall_s") if r.get("wall_s") is not None else r.get("run_s", 0.0))
            cpu = float(r.get("cpu_s") if r.get("cpu_s") is not None else 0.0)
            energy_j = compute_estimated_energy_joules(cpu, cpu_watts) or 0.0
            runs_o2.append({
                "wall_s": wall,
                "cpu_s": cpu,
                "est_energy_j": energy_j,
                "stdout": r.get("stdout", ""),
                "stderr": r.get("stderr", ""),
                "exit_code": r.get("exit_code", 0),
                "timed_out": bool(r.get("timed_out")),
            })

    med_o0_wall = round(statistics.median([r["wall_s"] for r in runs_o0]), 4)
    med_o0_cpu = round(statistics.median([r["cpu_s"] for r in runs_o0]), 4)
    med_o0_energy = round(statistics.median([r["est_energy_j"] for r in runs_o0]), 4)

    med_o2_wall = round(statistics.median([r["wall_s"] for r in runs_o2]), 4)
    med_o2_cpu = round(statistics.median([r["cpu_s"] for r in runs_o2]), 4)
    med_o2_energy = round(statistics.median([r["est_energy_j"] for r in runs_o2]), 4)

    def calc_pct(o0_val: float, o2_val: float) -> float:
        if o0_val > 0.0:
            return round((o0_val - o2_val) / o0_val * 100.0, 1)
        return 0.0

    energy_saved_pct = calc_pct(med_o0_energy, med_o2_energy)
    wall_saved_pct = calc_pct(med_o0_wall, med_o2_wall)
    cpu_saved_pct = calc_pct(med_o0_cpu, med_o2_cpu)

    out_o0 = runs_o0[0]["stdout"].strip()
    out_o2 = runs_o2[0]["stdout"].strip()
    code_o0 = runs_o0[0]["exit_code"]
    code_o2 = runs_o2[0]["exit_code"]

    outputs_differ = (out_o0 != out_o2) or (code_o0 != code_o2)
    diff_warning = (
        "Outputs differ between -O0 and -O2: possible undefined behaviour detected."
        if outputs_differ else None
    )

    return {
        "ok": True,
        "language": lang_id,
        "runs_count": 3,
        "o0": {
            "median_wall_s": med_o0_wall,
            "median_cpu_s": med_o0_cpu,
            "median_energy_j": med_o0_energy,
            "runs": runs_o0,
        },
        "o2": {
            "median_wall_s": med_o2_wall,
            "median_cpu_s": med_o2_cpu,
            "median_energy_j": med_o2_energy,
            "runs": runs_o2,
        },
        "saved": {
            "energy_pct": energy_saved_pct,
            "wall_pct": wall_saved_pct,
            "cpu_pct": cpu_saved_pct,
            "energy_j": round(max(0.0, med_o0_energy - med_o2_energy), 4),
        },
        "outputs_differ": outputs_differ,
        "diff_warning": diff_warning,
    }


# ──────────────────────────────────────────────────────────────────────────────
# HTTP layer
# ──────────────────────────────────────────────────────────────────────────────

POST_ROUTES = {
    "/api/cpp/analyze": api_cpp_analyze,
    "/api/cpp/heal": api_cpp_heal,
    "/api/cpp/compile": api_cpp_compile,
    "/api/cpp/run": api_cpp_run,
    "/api/cpp/ast": api_cpp_ast,
    "/api/analyze": api_cpp_analyze,
    "/api/heal": api_cpp_heal,
    "/api/compile": api_cpp_compile,
    "/api/run": api_cpp_run,
    "/api/ast": api_cpp_ast,
    "/api/samples": lambda body: api_samples(body.get("language", body.get("lang", "cpp"))),
    "/api/aai/scan": api_aai_scan,
    "/api/aai/verify-log": lambda _b: api_aai_verify_log(),
    "/api/energy/compare": api_energy_compare,
    "/api/cpp/energy/compare": api_energy_compare,
}
GET_ROUTES = {
    "/api/status": api_status,
    "/api/samples": api_samples,
    "/api/benchmark": api_benchmark,
    "/api/aai/samples": lambda: api_aai_samples(),
    "/api/aai/log": api_aai_log,
    "/api/aai/verify-log": api_aai_verify_log,
    "/api/aai/metrics": api_aai_metrics,
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
        if rel.startswith("static/"):
            rel = rel[len("static/"):]
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
        parsed = urlparse(self.path)
        path = parsed.path
        fn = GET_ROUTES.get(path)
        if fn:
            if path == "/api/samples":
                qs = parse_qs(parsed.query)
                lang = qs.get("language", qs.get("lang", ["cpp"]))[0]
                return self._run(fn, lang)
            if path == "/api/aai/log":
                qs = parse_qs(parsed.query)
                try:
                    limit = int(qs.get("limit", [500])[0])
                except ValueError:
                    limit = 500
                return self._run(fn, limit)
            return self._run(fn)
        if path.startswith("/results/"):
            rel = path[len("/results/"):].lstrip("/")
            target = (ROOT_DIR / "results" / rel).resolve()
            results_dir = (ROOT_DIR / "results").resolve()
            if results_dir not in target.parents and target != results_dir:
                return self._send_json({"error": "Not found"}, 404)
            if not target.is_file():
                return self._send_json({"error": "Not found"}, 404)
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("/api/"):
            return self._send_json({"error": "Unknown endpoint"}, 404)
        self._send_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        fn = POST_ROUTES.get(path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not fn:
            if 0 < length <= MAX_BODY_BYTES:
                try:
                    self.rfile.read(length)
                except Exception:
                    pass
            return self._send_json({"error": "Unknown endpoint"}, 404)
        if length <= 0 or length > MAX_BODY_BYTES:
            if length > MAX_BODY_BYTES:
                try:
                    self.rfile.read(min(length, 4096))
                except Exception:
                    pass
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
    global RUN_ENABLED
    _load_env()
    RUN_ENABLED = host in ("127.0.0.1", "localhost", "::1")
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
