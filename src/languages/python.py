"""
python.py
---------
Python language implementation targeting Python 3 runtime, py_compile, and ast module.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import Language, NotSupported, ToolchainNotFound, _scrub_paths, _to_jsonable

COMPILE_TIMEOUT_S = 10
RUN_TIMEOUT_S = 5
RUN_OUTPUT_CAP = 64 * 1024
RUN_STDIN_CAP = 64 * 1024

_SORRY_RE = re.compile(
    r"Sorry:\s*([A-Za-z0-9_]+Error):\s*(.+?)\s*\([^)]*line\s*(\d+)[^)]*\)"
)
_FILE_LINE_RE = re.compile(r'File\s+"[^"]*",\s*line\s*(\d+)')
_ERROR_TYPE_RE = re.compile(r"([A-Za-z0-9_]+Error):\s*(.*)")


def _categorize_python_error(err_type: str, msg: str) -> str:
    """Map error category by keyword (deterministic rule-based, no ML claim)."""
    et = err_type.lower()
    m = msg.lower()
    if "indent" in et or "indent" in m or "tab" in et:
        return "indentation_error"
    if "name" in et or "is not defined" in m or "undefined" in m:
        return "name_error"
    if "type" in et or "typeerror" in m:
        return "type_error"
    if "zero" in m or "division" in m:
        return "division_by_zero"
    if "index" in et or "indexerror" in m:
        return "index_error"
    if "key" in et or "keyerror" in m:
        return "key_error"
    if "attribute" in et or "attributeerror" in m:
        return "attribute_error"
    if "syntax" in et or "syntaxerror" in m:
        return "syntax_error"
    return "syntax_error"


class PythonLanguage(Language):
    """
    Python language implementation.
    - check: py_compile via subprocess 'python -I -m py_compile'.
    - run: 'python -I file.py' with stdin, 5 s timeout, 64 KB output cap.
    - tree: Python ast module converted to {type, details, label, line, end_line, children}.
    - safety: blocks dangerous system modules, shell calls, and unauthorized file writes.
    """

    id = "python"
    name = "Python"
    extensions = [".py"]

    def __init__(self) -> None:
        self.last_stderr: str = ""

    def toolchain_available(self) -> bool:
        """Check whether python runtime is available."""
        try:
            res = subprocess.run(
                [sys.executable, "-V"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    def is_safe(self, code: str) -> Tuple[bool, str]:
        """
        Safety check for Python execution.
        Blocks os.system, subprocess, eval(, exec(, __import__,
        open( with write modes outside the temp dir, socket,
        shutil.rmtree, and ctypes.
        """
        # Block os.system
        if re.search(r"\bos\s*\.\s*system\b", code):
            return (False, "Security Violation: 'os.system' is forbidden.")

        # Block subprocess
        if re.search(r"\bsubprocess\b", code):
            return (False, "Security Violation: 'subprocess' module is forbidden.")

        # Block eval(
        if re.search(r"\beval\s*\(", code):
            return (False, "Security Violation: 'eval()' is forbidden.")

        # Block exec(
        if re.search(r"\bexec\s*\(", code):
            return (False, "Security Violation: 'exec()' is forbidden.")

        # Block __import__
        if re.search(r"\b__import__\b", code):
            return (False, "Security Violation: '__import__' is forbidden.")

        # Block socket
        if re.search(r"\bsocket\b", code):
            return (False, "Security Violation: 'socket' module is forbidden.")

        # Block shutil.rmtree
        if re.search(r"\bshutil\s*\.\s*rmtree\b", code):
            return (False, "Security Violation: 'shutil.rmtree' is forbidden.")

        # Block ctypes
        if re.search(r"\bctypes\b", code):
            return (False, "Security Violation: 'ctypes' module is forbidden.")

        # Block open( with write modes outside temp dir
        safe_open, reason = self._check_safe_open(code)
        if not safe_open:
            return (False, reason)

        return (True, "")

    def _check_safe_open(self, code: str) -> Tuple[bool, str]:
        """Verify open() calls with write modes do not target files outside temporary dirs."""
        if not re.search(r"\bopen\s*\(", code):
            return (True, "")

        temp_dir = tempfile.gettempdir().lower()
        temp_prefixes = (temp_dir, "/tmp", "/var/tmp")

        # 1. AST check if code parses
        try:
            parsed = ast.parse(code)
            for node in ast.walk(parsed):
                if isinstance(node, ast.Call):
                    is_open = False
                    if isinstance(node.func, ast.Name) and node.func.id == "open":
                        is_open = True
                    elif isinstance(node.func, ast.Attribute) and node.func.attr == "open":
                        is_open = True

                    if is_open:
                        mode = "r"
                        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                            mode = node.args[1].value
                        for kw in node.keywords:
                            if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                                mode = kw.value.value

                        if any(ch in mode for ch in ("w", "a", "x", "+")):
                            if node.args:
                                arg0 = node.args[0]
                                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                                    val = arg0.value
                                    if ".." in val:
                                        return (False, "Security Violation: 'open()' with write mode outside temporary directory (path traversal '..') is forbidden.")
                                    if os.path.isabs(val):
                                        norm = os.path.normpath(val).lower().replace("\\", "/")
                                        if not any(norm.startswith(p.replace("\\", "/")) for p in temp_prefixes):
                                            return (False, f"Security Violation: 'open()' with write mode outside temporary directory ('{val}') is forbidden.")
        except Exception:
            pass

        # 2. Regex fallback for write modes
        write_open_pattern = re.compile(
            r'\bopen\s*\(\s*([^,)]+)\s*,\s*["\']([^"\']*[wax+][^"\']*)["\']',
            re.IGNORECASE,
        )
        for m in write_open_pattern.finditer(code):
            path_expr = m.group(1).strip()
            if ".." in path_expr:
                return (False, "Security Violation: 'open()' with write mode outside temporary directory (path traversal '..') is forbidden.")
            if re.search(r'^["\'](?:[a-zA-Z]:|[\\/])', path_expr):
                norm = path_expr.lower().replace("\\", "/")
                if not ("/tmp" in norm or "temp" in norm):
                    return (False, f"Security Violation: 'open()' with write mode outside temporary directory ({path_expr}) is forbidden.")

        return (True, "")

    def check(self, code: str, workdir: str) -> List[Dict[str, Any]]:
        """
        Compile code with py_compile via subprocess 'python -I -m py_compile'.
        Returns list of diagnostics: {file, line, column, type, message, raw, category, confidence}.
        """
        src = os.path.join(workdir, "main.py")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)

        safe, reason = self.is_safe(code)
        if not safe:
            self.last_stderr = f"error: {reason}"
            return [{
                "file": src,
                "line": 1,
                "column": 1,
                "type": "error",
                "message": reason,
                "raw": f"error: {reason}",
                "category": "security_violation",
                "confidence": 1.0,
            }]

        try:
            res = subprocess.run(
                [sys.executable, "-I", "-m", "py_compile", src],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=workdir,
                timeout=COMPILE_TIMEOUT_S,
            )
        except FileNotFoundError:
            self.last_stderr = "python interpreter not found"
            raise ToolchainNotFound("Python was not found on this machine. Install Python 3 and restart.")
        except subprocess.TimeoutExpired:
            self.last_stderr = "timeout"
            return [{
                "file": src,
                "line": 1,
                "column": 1,
                "type": "error",
                "message": f"Compilation timed out after {COMPILE_TIMEOUT_S}s.",
                "raw": "timeout",
                "category": "other",
                "confidence": 1.0,
            }]

        self.last_stderr = res.stderr
        if res.returncode == 0:
            # Check for static undefined names (NameError) if py_compile succeeded
            undefined_diagnostics = self._check_undefined_names(code, src)
            return undefined_diagnostics

        # Parse diagnostics from py_compile output
        diagnostics = self._parse_py_compile_output(res.stderr, src, code)
        return diagnostics

    def _parse_py_compile_output(self, stderr: str, src: str, code: str) -> List[Dict[str, Any]]:
        """Parse SyntaxError or IndentationError from py_compile stderr."""
        lines = stderr.splitlines()

        # Format 1: "Sorry: <ErrorType>: <message> (<file>, line <line>)"
        m_sorry = _SORRY_RE.search(stderr)
        if m_sorry:
            err_type = m_sorry.group(1)
            msg = m_sorry.group(2)
            line_no = int(m_sorry.group(3))
            cat = _categorize_python_error(err_type, msg)
            return [{
                "file": src,
                "line": line_no,
                "column": 1,
                "type": "error",
                "message": f"{err_type}: {msg}",
                "raw": stderr.strip(),
                "category": cat,
                "confidence": 1.0,
            }]

        # Format 2: Traceback style
        line_no = 1
        col = 1
        err_type = "SyntaxError"
        msg = "invalid syntax"

        m_line = _FILE_LINE_RE.search(stderr)
        if m_line:
            line_no = int(m_line.group(1))

        # Check for column caret (^)
        for l in lines:
            if "^" in l and not l.strip().startswith("File") and not "Error" in l:
                col = max(1, l.find("^") + 1)
                break

        m_err = _ERROR_TYPE_RE.search(stderr)
        if m_err:
            err_type = m_err.group(1)
            msg = m_err.group(2).strip()

        # Fallback to python compile() for exact line/col if needed
        try:
            compile(code, src, "exec")
        except (SyntaxError, IndentationError) as e:
            line_no = e.lineno or line_no
            col = e.offset or col
            err_type = type(e).__name__
            msg = e.msg or msg

        cat = _categorize_python_error(err_type, msg)
        return [{
            "file": src,
            "line": line_no,
            "column": col,
            "type": "error",
            "message": f"{err_type}: {msg}",
            "raw": stderr.strip(),
            "category": cat,
            "confidence": 1.0,
        }]

    def _check_undefined_names(self, code: str, src: str) -> List[Dict[str, Any]]:
        """Lightweight static check for undefined identifiers in functions."""
        import builtins
        import difflib

        builtin_names = set(dir(builtins))
        try:
            tree = ast.parse(code)
        except Exception:
            return []

        module_names: set = set()
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                module_names.add(stmt.name)
            for n in ast.walk(stmt):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    module_names.add(n.id)
                elif isinstance(n, (ast.Import, ast.ImportFrom)):
                    for alias in n.names:
                        module_names.add(alias.asname or alias.name.split(".")[0])

        diagnostics: List[Dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_defs = set(module_names) | builtin_names
                for a in node.args.args + node.args.kwonlyargs:
                    local_defs.add(a.arg)
                if node.args.vararg:
                    local_defs.add(node.args.vararg.arg)
                if node.args.kwarg:
                    local_defs.add(node.args.kwarg.arg)
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                        local_defs.add(sub.id)
                    elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        local_defs.add(sub.name)

                for sub in ast.walk(node):
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                        if sub.id not in local_defs:
                            candidates = [n for n in local_defs if not n.startswith("_")]
                            matches = difflib.get_close_matches(sub.id, candidates, n=1, cutoff=0.5)
                            sugg = f" Did you mean: '{matches[0]}'?" if matches else ""
                            msg = f"NameError: name '{sub.id}' is not defined.{sugg}"
                            diagnostics.append({
                                "file": src,
                                "line": getattr(sub, "lineno", 1),
                                "column": getattr(sub, "col_offset", 0) + 1,
                                "type": "error",
                                "message": msg,
                                "raw": msg,
                                "category": "name_error",
                                "confidence": 1.0,
                            })
                            return diagnostics  # Return primary issue

        return diagnostics

    def run(self, code: str, workdir: str, stdin: str = "", timeout: float = 5.0) -> Dict[str, Any]:
        """
        Run code via 'python -I main.py' with stdin, 5 s timeout, and 64 KB output cap.
        Returns: {stdout, stderr, exit_code, timed_out}.
        """
        safe, reason = self.is_safe(code)
        if not safe:
            return {
                "stdout": "",
                "stderr": f"Execution blocked: {reason}",
                "exit_code": 1,
                "timed_out": False,
            }

        src = os.path.join(workdir, "main.py")
        if not os.path.isfile(src):
            with open(src, "w", encoding="utf-8") as f:
                f.write(code)

        stdin_data = (stdin or "")[:RUN_STDIN_CAP]
        t_limit = min(max(0.5, float(timeout)), RUN_TIMEOUT_S)

        try:
            proc = subprocess.Popen(
                [sys.executable, "-I", src],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=workdir,
            )
            try:
                out, err = proc.communicate(input=stdin_data, timeout=t_limit)
                timed_out = False
                code_ret = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
                timed_out = True
                code_ret = -1
                err = (err or "") + f"\nExecution timed out (limit: {t_limit:.1f} s)."
            finally:
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Runtime execution failed: {type(e).__name__}: {e}",
                "exit_code": 1,
                "timed_out": False,
            }

        truncated = False
        # Truncate output at 64 KB
        if len(out) > RUN_OUTPUT_CAP:
            out = out[:RUN_OUTPUT_CAP] + "\n[output truncated at 64 KB]"
            truncated = True
        if len(err) > RUN_OUTPUT_CAP:
            err = err[:RUN_OUTPUT_CAP] + "\n[output truncated at 64 KB]"
            truncated = True

        # Scrub temp directory from output paths
        prefixes = [workdir + os.sep, workdir + "/", workdir]
        out = _scrub_paths(out, prefixes)
        err = _scrub_paths(err, prefixes)

        return {
            "stdout": out,
            "stderr": err,
            "exit_code": code_ret,
            "timed_out": timed_out,
            "truncated": truncated,
        }

    def tree(self, code: str) -> List[Dict[str, Any]]:
        """
        Extract AST using Python's ast module into {type, details, label, line, end_line, children}.
        """
        try:
            parsed = ast.parse(code)
        except (SyntaxError, IndentationError) as e:
            raise ValueError(f"SyntaxError on line {e.lineno}: {e.msg}")

        def _to_node(node: ast.AST) -> Dict[str, Any]:
            node_type = node.__class__.__name__
            line = getattr(node, "lineno", None)
            end_line = getattr(node, "end_lineno", line)

            parts: List[str] = []
            label = ""

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                parts.append(f"name='{node.name}'")
                label = node.name
            elif isinstance(node, ast.Name):
                parts.append(f"id='{node.id}'")
                label = node.id
            elif isinstance(node, ast.Constant):
                parts.append(f"value={repr(node.value)}")
                label = repr(node.value)
            elif isinstance(node, ast.Attribute):
                parts.append(f"attr='{node.attr}'")
                label = node.attr
            elif isinstance(node, ast.arg):
                parts.append(f"arg='{node.arg}'")
                label = node.arg
            elif isinstance(node, ast.BinOp):
                parts.append(f"op={node.op.__class__.__name__}")
                label = node.op.__class__.__name__
            elif isinstance(node, ast.UnaryOp):
                parts.append(f"op={node.op.__class__.__name__}")
                label = node.op.__class__.__name__
            elif isinstance(node, ast.Compare):
                ops = ", ".join(o.__class__.__name__ for o in node.ops)
                parts.append(f"ops={ops}")
                label = ops
            else:
                for field, val in ast.iter_fields(node):
                    if isinstance(val, (str, int, float, bool)) and field not in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
                        parts.append(f"{field}={repr(val)}")
                label = ", ".join(parts) if parts else node_type

            details = ", ".join(parts)
            children = [_to_node(child) for child in ast.iter_child_nodes(node)]

            return {
                "type": node_type,
                "details": details,
                "label": label or details or node_type,
                "line": line,
                "end_line": end_line,
                "children": children,
            }

        root = _to_node(parsed)
        return [root]
