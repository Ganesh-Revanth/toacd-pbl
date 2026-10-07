import subprocess
import re
import os

def _sanitize_code(source: str, permissions: dict = None) -> bool:
    if permissions is None:
        permissions = {
            "allow_system_calls": os.environ.get("ALLOW_SYSTEM_CALLS") == "1",
            "allow_assembly": os.environ.get("ALLOW_ASSEMBLY") == "1",
            "allow_sys_includes": os.environ.get("ALLOW_SYS_INCLUDES") == "1",
        }
    
    dangerous_patterns = []
    
    if not permissions.get("allow_system_calls", False):
        dangerous_patterns.extend([r'system\s*\(', r'exec\s*\(', r'popen\s*\(', r'fork\s*\('])
        
    if not permissions.get("allow_assembly", False):
        dangerous_patterns.extend([r'__asm__', r'shellcode'])
        
    if not permissions.get("allow_sys_includes", False):
        dangerous_patterns.extend([r'#include\s*[<"]\s*sys/'])

    for pattern in dangerous_patterns:
        if re.search(pattern, source):
            return False
    return True

def _sanitize_input(file_path: str, permissions: dict = None) -> bool:
    if not os.path.exists(file_path):
        return True
    with open(file_path, 'r', errors='ignore') as f:
        return _sanitize_code(f.read(), permissions)

import sys
import shutil

def get_compiler_cmd_and_env():
    """
    Finds a suitable C++ compiler (g++) and configures the environment.
    On Windows, searches common MinGW/MSYS2 locations and ensures the bin
    folder is included in PATH for DLL resolution without shadowing system Python.
    """
    env = os.environ.copy()
    which_gpp = shutil.which("g++")
    if which_gpp:
        return which_gpp, env

    if sys.platform == "win32" or os.name == "nt":
        candidates = [
            r"C:\msys64\ucrt64\bin\g++.exe",
            r"C:\msys64\mingw64\bin\g++.exe",
            r"C:\MinGW\bin\g++.exe",
            r"C:\mingw64\bin\g++.exe",
            r"C:\w64devkit\bin\g++.exe",
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                bin_dir = os.path.dirname(candidate)
                current_path = env.get("PATH", "")
                if bin_dir.lower() not in current_path.lower():
                    env["PATH"] = current_path + os.pathsep + bin_dir
                return candidate, env

    return "g++", env

def run_cpp_compiler(file_path, permissions=None):
    if not _sanitize_input(file_path, permissions):
        return [{
            "file": file_path,
            "line": 1,
            "column": 1,
            "type": "error",
            "message": "Security Error: Malicious command injection or forbidden system call detected.",
            "raw": "error: Malicious command injection or forbidden system call detected."
        }]
    compiler_bin, env = get_compiler_cmd_and_env()
    try:
        res=subprocess.run(
            [compiler_bin,"-std=c++17",file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        errors=[]
        pattern=r"(.+):(\d+):(\d+):\s+(error|warning):\s+(.*)"

        for line in res.stderr.splitlines():
            match=re.match(pattern, line)
            if match:
                errors.append({
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "column": int(match.group(3)),
                    "type": match.group(4),
                    "message": match.group(5),
                    "raw": line
                })
        return errors

    except (FileNotFoundError, OSError):
        return[{
            "file":None,
            "line":None,
            "column":None,
            "type":"error",
            "message":"g++ compiler not found.",
            "raw":"g++ compiler not found."
        }]