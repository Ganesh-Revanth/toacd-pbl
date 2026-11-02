"""
cpp.py
------
C++ language implementation using g++ and clang++.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import Language, NotSupported, ToolchainNotFound, _scrub_paths, _to_jsonable
from energy_meter import ProcessMonitor, read_rapl_energy_joules, is_psutil_available

COMPILE_TIMEOUT_S = 30
RUN_TIMEOUT_S = 5
RUN_OUTPUT_CAP = 64 * 1024
RUN_STDIN_CAP = 64 * 1024
OUT_NAME = "out.exe" if os.name == "nt" else "out.bin"

_ERR_PATTERN = re.compile(r"^(.+?):(\d+):(\d+):\s*(error|warning):\s*(.*)$")


def _limit_child() -> None:  # pragma: no cover - runs in the child, POSIX only
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (RUN_TIMEOUT_S + 2, RUN_TIMEOUT_S + 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (RUN_OUTPUT_CAP * 4, RUN_OUTPUT_CAP * 4))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64)) if hasattr(resource, "RLIMIT_NPROC") else None
    try:
        resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    except (ValueError, OSError):
        pass


class CppLanguage(Language):
    """C++ language implementation targeting g++ compiler and clang++ AST extractor."""

    id = "cpp"
    name = "C++"
    extensions = [".cpp", ".cc", ".cxx", ".h", ".hpp"]

    def __init__(self) -> None:
        self.last_stderr: str = ""
        self.last_compile_metrics: Dict[str, Optional[float]] = {"wall_s": None, "cpu_s": None}

    def is_safe(self, code: str) -> Tuple[bool, str]:
        """Check if code avoids forbidden system calls, shellcode, or dangerous includes."""
        from compiler_runner import _sanitize_code
        if not _sanitize_code(code):
            return (False, "Security Error: Malicious command injection or forbidden system call detected.")
        return (True, "")

    def toolchain_available(self) -> bool:
        """Check whether g++ is found in PATH or in standard MinGW/MSYS2 locations."""
        try:
            from compiler_runner import get_compiler_cmd_and_env
            gxx, env = get_compiler_cmd_and_env()
            return bool(shutil.which(gxx, path=env.get("PATH")) or os.path.isfile(gxx))
        except Exception:
            return bool(shutil.which("g++"))

    def check(self, code: str, workdir: str) -> List[Dict[str, Any]]:
        """Compile code with g++ inside workdir. Returns list of diagnostics."""
        from compiler_runner import get_compiler_cmd_and_env

        src = os.path.join(workdir, "main.cpp")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)

        safe, reason = self.is_safe(code)
        if not safe:
            self.last_stderr = "error: Malicious code blocked"
            return [{
                "file": src, "line": 1, "column": 1, "type": "error",
                "message": reason,
                "raw": "error: Malicious code blocked",
                "category": "security_violation", "confidence": 1.0,
            }]

        gxx, env = get_compiler_cmd_and_env()
        env = {**env, "LC_ALL": "C", "LANGUAGE": "C"}
        out_path = os.path.join(workdir, OUT_NAME)
        t_comp_start = time.perf_counter()
        try:
            proc = subprocess.Popen(
                [gxx, "-std=c++17", "-Wall", src, "-o", out_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", env=env,
                cwd=workdir,
            )
            monitor = ProcessMonitor(proc.pid, interval=0.01)
            monitor.start()
            out, err = proc.communicate(timeout=COMPILE_TIMEOUT_S)
            monitor.stop(proc)
            comp_wall = time.perf_counter() - t_comp_start
            self.last_compile_metrics = {
                "wall_s": round(comp_wall, 4) if is_psutil_available() else None,
                "cpu_s": round(monitor.cpu_time_s, 4) if is_psutil_available() else None,
            }
            res = subprocess.CompletedProcess(proc.args, proc.returncode, out, err)
        except FileNotFoundError:
            self.last_stderr = "g++ not found"
            self.last_compile_metrics = {"wall_s": None, "cpu_s": None}
            raise ToolchainNotFound("g++ was not found on this machine. Install a C++ toolchain and restart.")
        except subprocess.TimeoutExpired:
            self.last_stderr = "timeout"
            self.last_compile_metrics = {"wall_s": None, "cpu_s": None}
            return [{
                "file": src, "line": 1, "column": 1, "type": "error",
                "message": f"Compilation timed out after {COMPILE_TIMEOUT_S}s.",
                "raw": "timeout", "category": "other", "confidence": 1.0,
            }]

        self.last_stderr = res.stderr
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
        return errors

    def run(self, code: str, workdir: str, stdin: str = "", timeout: float = RUN_TIMEOUT_S) -> Dict[str, Any]:
        """Compile (if needed) and run the binary with stdin and timeout."""
        exe = os.path.join(workdir, OUT_NAME)
        if not os.path.isfile(exe):
            errors = self.check(code, workdir)
            hard = sum(1 for e in errors if e.get("type") == "error")
            if hard > 0 or not os.path.isfile(exe):
                return {
                    "stdout": "",
                    "stderr": self.last_stderr.strip() or "Compilation failed",
                    "exit_code": -1,
                    "timed_out": False,
                    "truncated": False,
                    "crashed": False,
                    "run_s": 0.0,
                }
        from compiler_runner import get_compiler_cmd_and_env
        _, env = get_compiler_cmd_and_env()
        return self._run_binary(exe, workdir, stdin, env, timeout=timeout)

    def _run_binary(self, exe: str, workdir: str, stdin_text: str, env: Dict[str, str], timeout: float = RUN_TIMEOUT_S) -> Dict[str, Any]:
        """Run a compiled program with a timeout, an output cap and (on POSIX) resource limits."""
        t0 = time.perf_counter()
        kw: Dict[str, Any] = {}
        if os.name != "nt":
            kw["preexec_fn"] = _limit_child
        proc = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=workdir, env=env, **kw)
        monitor = ProcessMonitor(proc.pid, interval=0.01)
        monitor.start()
        rapl_start = read_rapl_energy_joules()

        chunks = {"out": bytearray(), "err": bytearray()}
        truncated = threading.Event()

        def pump(stream, key):
            try:
                while True:
                    b = stream.read(4096)
                    if not b:
                        return
                    room = RUN_OUTPUT_CAP - len(chunks[key])
                    if room > 0:
                        chunks[key] += b[:room]
                    if len(b) > room:
                        truncated.set()
                        proc.kill()
                        return
            except Exception:
                return

        readers = [threading.Thread(target=pump, args=(proc.stdout, "out"), daemon=True),
                   threading.Thread(target=pump, args=(proc.stderr, "err"), daemon=True)]
        for r in readers:
            r.start()

        def feed():
            try:
                proc.stdin.write(stdin_text.encode("utf-8"))
            except Exception:
                pass
            finally:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
        threading.Thread(target=feed, daemon=True).start()

        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()

        monitor.stop(proc)
        rapl_end = read_rapl_energy_joules()
        wall_s = time.perf_counter() - t0

        for r in readers:
            r.join(timeout=1)
        for s in (proc.stdout, proc.stderr):
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        code = proc.returncode
        rapl_j = max(0.0, rapl_end - rapl_start) if (rapl_start is not None and rapl_end is not None) else None
        metrics = monitor.get_metrics(wall_s=wall_s)

        return {
            "stdout": chunks["out"].decode("utf-8", "replace"),
            "stderr": chunks["err"].decode("utf-8", "replace"),
            "exit_code": code,
            "timed_out": timed_out,
            "truncated": truncated.is_set(),
            "crashed": (not timed_out) and not truncated.is_set() and code is not None and (code < 0 or code >= 0xC0000000),
            "run_s": round(wall_s, 3),
            "wall_s": metrics["wall_s"],
            "cpu_s": metrics["cpu_s"],
            "peak_mem_mb": metrics["peak_mem_mb"],
            "rapl_j": rapl_j,
        }

    def tree(self, code: str) -> Any:
        """Extract AST using clang++ and return cleaned tree."""
        if not shutil.which("clang++"):
            raise NotSupported("clang++ was not found. Install clang to use the C++ AST view.")
        from ast_extractor import extract_ast, parse_ast_to_tree
        with tempfile.TemporaryDirectory(prefix="webui_") as wd:
            src = os.path.join(wd, "main.cpp")
            with open(src, "w", encoding="utf-8") as f:
                f.write(code)
            text = extract_ast(src)
            tree_data = parse_ast_to_tree(text, src)
            scrubbed = _scrub_paths(_to_jsonable(tree_data), [wd + os.sep, wd.replace("\\", "/") + "/", wd])
            return scrubbed
