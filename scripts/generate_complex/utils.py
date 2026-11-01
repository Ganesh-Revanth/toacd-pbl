"""
scripts/generate_complex/utils.py
---------------------------------
Utilities for complex benchmark generation and validation:
- Line count assertions (150-500 lines)
- Toolchain validation (g++, gcc, python, javac)
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple


def validate_and_write(path: Path, code: str, expect_compile: bool = True, lang: str = "cpp") -> Tuple[bool, int, str]:
    """
    Validates code constraints and writes to file:
      1. Line count must be within [150, 500].
      2. If expect_compile is True, verifies compilation succeeds with 0 errors.
      3. If expect_compile is False, verifies compilation fails with >=1 error.
    Returns: (success, line_count, message)
    """
    lines = code.strip().splitlines()
    line_count = len(lines)
    
    if line_count < 150 or line_count > 500:
        return False, line_count, f"Line count {line_count} outside allowed [150, 500] range."

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code.strip() + "\n")

    # Compiler validation check
    compile_ok, msg = check_compilation(str(path), lang)
    if expect_compile and not compile_ok:
        return False, line_count, f"Compilation failed unexpectedly: {msg}"
    if not expect_compile and compile_ok:
        return False, line_count, "Expected compilation to fail, but it compiled cleanly."

    return True, line_count, "OK"


def check_compilation(file_path: str, lang: str) -> Tuple[bool, str]:
    """Runs the appropriate compiler on file_path in a temp dir to verify buildability."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_bin = os.path.join(tmp_dir, "test_out.exe" if os.name == "nt" else "test_out")
        
        try:
            if lang == "cpp":
                cmd = ["g++", "-std=c++17", "-O0", file_path, "-o", out_bin]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                return (res.returncode == 0, res.stderr)
            elif lang == "c":
                cmd = ["gcc", "-std=c11", "-O0", file_path, "-o", out_bin]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                return (res.returncode == 0, res.stderr)
            elif lang == "python":
                cmd = ["python", "-m", "py_compile", file_path]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
                return (res.returncode == 0, res.stderr)
            elif lang == "java":
                cmd = ["javac", "-d", tmp_dir, file_path]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                return (res.returncode == 0, res.stderr)
            else:
                return True, "Unknown language"
        except subprocess.TimeoutExpired:
            return False, "Compilation timed out"
        except Exception as e:
            return False, str(e)

