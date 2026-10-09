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


def compile_code(code: str, file_path: Optional[str] = None) -> dict:
    """
    Tool: Compiles the C++ source code using GCC and returns structured diagnostics.
    Always tests the updated in-memory `code` buffer.
    """
    temp = tempfile.NamedTemporaryFile("w", suffix=".cpp", delete=False, encoding="utf-8")
    temp.write(code)
    temp.flush()
    temp.close()
    temp_file = temp.name

    try:
        errors, raw_stderr = _compile(temp_file)
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
            "raw_stderr": raw_stderr.strip(),
        }
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass


def security_audit(code: str, file_path: Optional[str] = None, errors: list = None) -> dict:
    """
    Tool: Runs static vulnerability analysis and security scanning on the C++ code.
    Returns risk score, risk level, and detected vulnerabilities.
    Always tests the updated in-memory `code` buffer.
    """
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


def try_fast_heal(code: str, error: dict) -> Optional[str]:
    """
    Tool: Invokes Tier 1 heuristic auto-healer for instant quick fixes.
    Returns patched code string or None.
    """
    return attempt_fix(code, error)
