"""
java.py
-------
Java language implementation targeting javac compiler and java runtime.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import Language, NotSupported, ToolchainNotFound, _scrub_paths, _to_jsonable

COMPILE_TIMEOUT_S = 15
RUN_TIMEOUT_S = 5
RUN_OUTPUT_CAP = 64 * 1024
RUN_STDIN_CAP = 64 * 1024

_JAVAC_ERR_RE = re.compile(r"^(.+?\.java):(\d+):\s*(error|warning):\s*(.*)$")


def _detect_class_name(code: str) -> str:
    """
    Detect the class name for the compilation unit.
    The public class name decides the file name (default Main.java; detect 'public class X').
    """
    # 1. Search for public class / interface / enum / record X
    m = re.search(
        r"\bpublic\s+(?:final\s+|abstract\s+)?(?:class|interface|enum|record)\s+([A-Za-z0-9_]+)\b",
        code,
    )
    if m:
        return m.group(1)

    # 2. Search for any class X
    m2 = re.search(r"\bclass\s+([A-Za-z0-9_]+)\b", code)
    if m2:
        return m2.group(1)

    return "Main"


def _categorize_java_error(msg: str) -> str:
    """Map error category by keyword (deterministic, no ML claim)."""
    m = msg.lower()
    if "expected" in m or "invalid method declaration" in m or "illegal start of" in m or "not a statement" in m:
        return "syntax_error"
    if "cannot find symbol" in m or "symbol not found" in m:
        return "name_error"
    if "incompatible types" in m or "cannot be converted" in m or "lossy conversion" in m:
        return "type_error"
    if "unreachable statement" in m:
        return "control_flow_error"
    if "missing return statement" in m:
        return "syntax_error"
    return "syntax_error"


class JavaLanguage(Language):
    """
    Java language implementation.
    - check: javac in a temp dir, parsing 'File.java:LINE: error: MESSAGE' + caret column.
    - run: java -cp dir X with stdin, 5 s timeout, 64 KB output cap.
    - tree: raises NotSupported('no syntax tree for Java yet').
    - safety: blocks ProcessBuilder, Runtime.getRuntime().exec, System.exit, java.net, File deletes outside temp, reflection loaders.
    """

    id = "java"
    name = "Java"
    extensions = [".java"]

    def __init__(self) -> None:
        self.last_stderr: str = ""

    def toolchain_available(self) -> bool:
        """Check whether javac and java are available in PATH."""
        javac_bin = shutil.which("javac")
        java_bin = shutil.which("java")
        return bool(javac_bin and java_bin)

    def is_safe(self, code: str) -> Tuple[bool, str]:
        """
        Safety check for Java execution.
        Blocks:
        - Runtime.getRuntime().exec
        - ProcessBuilder
        - System.exit(
        - java.net
        - java.io.File deletes outside the temp dir
        - reflection loaders (ClassLoader, Class.forName, java.lang.reflect, Method.invoke)
        """
        # Block reflection loaders
        if re.search(r"\b(ClassLoader|Class\.forName|java\.lang\.reflect|Method\.invoke)\b", code):
            return (False, "Security Violation: Reflection and dynamic class loading are forbidden.")

        # Block Runtime.getRuntime().exec / Runtime command execution
        if re.search(r"\bRuntime\s*\.\s*getRuntime\b", code) or re.search(r"\bRuntime\b", code):
            return (False, "Security Violation: 'Runtime.getRuntime().exec' is forbidden.")

        # Block ProcessBuilder
        if re.search(r"\bProcessBuilder\b", code):
            return (False, "Security Violation: 'ProcessBuilder' is forbidden.")

        # Block System.exit(
        if re.search(r"\bSystem\s*\.\s*exit\s*\(", code):
            return (False, "Security Violation: 'System.exit()' is forbidden.")

        # Block java.net
        if re.search(r"\bjava\s*\.\s*net\b", code):
            return (False, "Security Violation: Network operations via 'java.net' are forbidden.")

        # Block java.io.File deletes outside temp dir
        safe_delete, del_reason = self._check_safe_file_delete(code)
        if not safe_delete:
            return (False, del_reason)

        return (True, "")

    def _check_safe_file_delete(self, code: str) -> Tuple[bool, str]:
        """Verify file deletion calls do not target files outside temporary dirs."""
        if not re.search(r"\.(?:delete|deleteOnExit)\s*\(", code) and not re.search(r"Files\s*\.\s*delete", code):
            return (True, "")

        # Look for suspicious path strings
        temp_dir = tempfile.gettempdir().lower()
        temp_prefixes = (temp_dir, "/tmp", "/var/tmp")

        for m in re.finditer(r'["\']([^"\']+)["\']', code):
            path_val = m.group(1)
            if ".." in path_val:
                return (False, "Security Violation: File deletion with path traversal ('..') is forbidden.")
            if os.path.isabs(path_val):
                norm = os.path.normpath(path_val).lower().replace("\\", "/")
                if not any(norm.startswith(p.replace("\\", "/")) for p in temp_prefixes):
                    return (False, f"Security Violation: File deletion outside temporary directory ('{path_val}') is forbidden.")

        # If bare delete is called on file instances created from non-temp paths
        if re.search(r'new\s+File\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\.delete', code):
            m_path = re.search(r'new\s+File\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\.delete', code)
            if m_path:
                pval = m_path.group(1).lower().replace("\\", "/")
                if not ("/tmp" in pval or "temp" in pval):
                    return (False, f"Security Violation: File deletion outside temporary directory ('{m_path.group(1)}') is forbidden.")

        return (True, "")

    def check(self, code: str, workdir: str) -> List[Dict[str, Any]]:
        """
        Compile code with javac in workdir.
        Returns list of diagnostics: {file, line, column, type, message, raw, category, confidence}.
        """
        class_name = _detect_class_name(code)
        file_name = f"{class_name}.java"
        src = os.path.join(workdir, file_name)
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

        javac_bin = shutil.which("javac")
        if not javac_bin:
            self.last_stderr = "javac not found"
            raise ToolchainNotFound("javac was not found on this machine. Install a JDK and restart.")

        try:
            res = subprocess.run(
                [javac_bin, "-d", workdir, src],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=workdir,
                timeout=COMPILE_TIMEOUT_S,
            )
        except FileNotFoundError:
            self.last_stderr = "javac not found"
            raise ToolchainNotFound("javac was not found on this machine. Install a JDK and restart.")
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
        diagnostics = self._parse_javac_output(res.stderr, src)
        return diagnostics

    def _parse_javac_output(self, stderr: str, src: str) -> List[Dict[str, Any]]:
        """
        Parse javac output:
        'File.java:LINE: error: MESSAGE'
        plus the caret line for the column.
        """
        if not stderr.strip():
            return []

        lines = stderr.splitlines()
        diagnostics: List[Dict[str, Any]] = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            m = _JAVAC_ERR_RE.match(line)
            if m:
                err_file = m.group(1)
                line_no = int(m.group(2))
                err_type = m.group(3)  # "error" or "warning"
                message = m.group(4).strip()
                col = 1
                raw_lines = [line]

                # Lookahead for code line, caret column, and symbol details
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if _JAVAC_ERR_RE.match(next_line.strip()) or next_line.strip().endswith("error") or next_line.strip().endswith("errors"):
                        break
                    raw_lines.append(next_line)
                    if "^" in next_line:
                        col = max(1, next_line.find("^") + 1)
                    elif "symbol:" in next_line:
                        sym_info = next_line.strip()
                        if "cannot find symbol" in message:
                            message = f"{message} ({sym_info})"
                    j += 1

                raw_block = "\n".join(raw_lines)
                cat = _categorize_java_error(message)

                diagnostics.append({
                    "file": err_file or src,
                    "line": line_no,
                    "column": col,
                    "type": err_type,
                    "message": message,
                    "raw": raw_block,
                    "category": cat,
                    "confidence": 1.0,
                })
                i = j
            else:
                i += 1

        return diagnostics

    def run(self, code: str, workdir: str, stdin: str = "", timeout: float = 5.0) -> Dict[str, Any]:
        """
        Run code via 'java -cp dir X' with stdin, 5 s timeout, and 64 KB output cap.
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

        java_bin = shutil.which("java")
        if not java_bin:
            return {
                "stdout": "",
                "stderr": "Runtime error: 'java' launcher not found.",
                "exit_code": 1,
                "timed_out": False,
            }

        class_name = _detect_class_name(code)
        stdin_data = (stdin or "")[:RUN_STDIN_CAP]
        t_limit = min(max(0.5, float(timeout)), RUN_TIMEOUT_S)

        try:
            proc = subprocess.Popen(
                [java_bin, "-cp", workdir, class_name],
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
        if len(out) > RUN_OUTPUT_CAP:
            out = out[:RUN_OUTPUT_CAP] + "\n[output truncated at 64 KB]"
            truncated = True
        if len(err) > RUN_OUTPUT_CAP:
            err = err[:RUN_OUTPUT_CAP] + "\n[output truncated at 64 KB]"
            truncated = True

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

    def tree(self, code: str) -> Any:
        """
        Syntax tree extraction for Java.
        Currently unsupported.
        """
        raise NotSupported("no syntax tree for Java yet")

