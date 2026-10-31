"""
agent_tools.py
--------------
Exposes GCC compilation, static security analysis, AST inspection,
and heuristic healing as structured, callable tools for the Agentic AI.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from compiler_runner import get_compiler_cmd_and_env
from heal_loop import _compile
from security_analyzer import analyze as analyze_security, format_security_report
from auto_healer import attempt_fix


def _resolve_language(language: Optional[Any], file_path: Optional[str]) -> Any:
    from languages import get_language, Language
    if isinstance(language, Language):
        return language
    if isinstance(language, str):
        return get_language(language) or get_language("cpp")
    if file_path:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".py", ".pyw"):
            return get_language("python")
        if ext in (".java",):
            return get_language("java")
        if ext in (".c", ".h"):
            return get_language("c")
    return get_language("cpp")


def compile_code(code: str, file_path: Optional[str] = None, language: Optional[Any] = None) -> dict:
    """
    Tool: Compiles the source code using the language registry's check() method and returns structured diagnostics.
    Always tests the updated in-memory `code` buffer.
    """
    lang = _resolve_language(language, file_path)

    with tempfile.TemporaryDirectory() as wd:
        try:
            errors = lang.check(code, wd)
        except Exception as exc:
            return {
                "success": False,
                "error_count": 1,
                "warning_count": 0,
                "errors": [{"line": 1, "column": 1, "type": "error", "message": str(exc), "raw": str(exc)}],
                "raw_stderr": str(exc),
            }

        hard_errors = [e for e in errors if e.get("type") == "error"]
        warnings = [e for e in errors if e.get("type") == "warning"]

        return {
            "success": len(hard_errors) == 0,
            "error_count": len(hard_errors),
            "warning_count": len(warnings),
            "errors": [
                {
                    "line": e.get("line"),
                    "column": e.get("column"),
                    "type": e.get("type"),
                    "message": e.get("message"),
                    "raw": e.get("raw"),
                }
                for e in errors
            ],
            "raw_stderr": getattr(lang, "last_stderr", "").strip(),
        }


def security_audit(code: str, file_path: Optional[str] = None, errors: list = None, language: Optional[Any] = None) -> dict:
    """
    Tool: Runs static vulnerability analysis and security scanning on the code.
    For Python/Java, verifies language safety policies. For C++/C, runs full AST security analysis.
    """
    lang = _resolve_language(language, file_path)

    if lang.id in ("python", "java"):
        safe, reason = lang.is_safe(code)
        if not safe:
            finding = {
                "file": file_path or f"main{lang.extensions[0]}",
                "line": 1,
                "column": 1,
                "severity": "Critical",
                "vulnerability_type": "Security Violation",
                "description": reason,
                "recommendation": "Remove forbidden system call or unsafe operation.",
                "source": "static_scan",
            }
            return {
                "risk_score": 100,
                "risk_level": "Critical",
                "is_secure": False,
                "findings_count": 1,
                "findings": [finding],
                "summary": f"Security Violation: {reason}",
            }
        return {
            "risk_score": 0,
            "risk_level": "Clean",
            "is_secure": True,
            "findings_count": 0,
            "findings": [],
            "summary": "Clean security profile.",
        }

    temp = tempfile.NamedTemporaryFile("w", suffix=".cpp", delete=False, encoding="utf-8")
    temp.write(code)
    temp.flush()
    temp.close()
    temp_file = temp.name

    try:
        findings = analyze_security(temp_file, errors or [])
        score = sum(
            {"Critical": 10, "High": 5, "Medium": 2, "Low": 1}.get(f.severity, 1)
            for f in findings
        )
        report = format_security_report(findings)
        critical_or_high = [f for f in findings if f.severity in ("Critical", "High")]

        return {
            "risk_score": score,
            "risk_level": "Clean" if score == 0 else ("Low" if score <= 10 else ("Medium" if score <= 30 else "High")),
            "is_secure": score <= 10 and len(critical_or_high) == 0,
            "findings_count": len(findings),
            "findings": [f.to_dict() for f in findings],
            "summary": report.strip(),
        }
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass


def inspect_ast(code: str) -> dict:
    """
    Tool: Inspects function signatures, classes, and include statements in the code.
    """
    try:
        from ast_extractor import extract_ast
        temp = tempfile.NamedTemporaryFile("w", suffix=".cpp", delete=False, encoding="utf-8")
        temp.write(code)
        temp.flush()
        temp.close()
        try:
            nodes = extract_ast(temp.name)
            return {
                "success": True,
                "node_count": len(nodes),
                "nodes": nodes[:50],
            }
        finally:
            if os.path.exists(temp.name):
                os.remove(temp.name)
    except Exception as exc:
        return {"success": False, "error": str(exc), "nodes": []}


def try_fast_heal(code: str, error: dict, language: Optional[Any] = None) -> Optional[str]:
    """
    Tool: Invokes Tier 1 heuristic auto-healer for instant quick fixes.
    Returns patched code string or None.
    """
    lang = _resolve_language(language, None)
    if lang.id == "python":
        try:
            from languages.python_rules import attempt_fix_python
            res = attempt_fix_python(code, error)
            if res:
                return res
        except Exception:
            pass
    elif lang.id == "java":
        try:
            from languages.java_rules import attempt_fix_java
            res = attempt_fix_java(code, error)
            if res:
                return res
        except Exception:
            pass
    return attempt_fix(code, error)
