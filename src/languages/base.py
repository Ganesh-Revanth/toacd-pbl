"""
base.py
-------
Base interface and exceptions for multi-language compilation and execution.
"""

from __future__ import annotations

import abc
import dataclasses
from typing import Any, Dict, List, Tuple


class NotSupported(Exception):
    """Raised when an operation (such as AST extraction) is not supported for a language."""
    pass


class ToolchainNotFound(Exception):
    """Raised when the required toolchain (compiler or runtime) is not installed."""
    pass


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses and collections to JSON-serializable types."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _scrub_paths(obj: Any, prefixes: List[str]) -> Any:
    """Remove temp directory paths from all strings in nested data structures."""
    if isinstance(obj, str):
        for pre in prefixes:
            obj = obj.replace(pre, "")
        return obj
    if isinstance(obj, list):
        return [_scrub_paths(x, prefixes) for x in obj]
    if isinstance(obj, dict):
        return {k: _scrub_paths(v, prefixes) for k, v in obj.items()}
    return obj


class Language(abc.ABC):
    """
    Abstract base class for programming languages supported by the platform.
    """
    id: str = ""
    name: str = ""
    extensions: List[str] = []

    @abc.abstractmethod
    def check(self, code: str, workdir: str) -> List[Dict[str, Any]]:
        """
        Compile or analyze code in workdir.
        Returns a list of diagnostics: {line, column, type, message, raw}.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run(self, code: str, workdir: str, stdin: str = "", timeout: float = 5.0) -> Dict[str, Any]:
        """
        Run the program with stdin and timeout.
        Returns: {stdout, stderr, exit_code, timed_out}.
        """
        raise NotImplementedError

    def is_safe(self, code: str) -> Tuple[bool, str]:
        """
        Check if code is safe to execute.
        Returns (is_safe: bool, reason: str).
        """
        return (True, "")

    @abc.abstractmethod
    def toolchain_available(self) -> bool:
        """
        Check if required compiler/runtime toolchain is available on this machine.
        """
        raise NotImplementedError

    def tree(self, code: str) -> Any:
        """
        Extract AST / syntax tree from code.
        Raises NotSupported if not supported for this language.
        """
        raise NotSupported(f"Syntax tree not supported for {self.name or self.id}")

