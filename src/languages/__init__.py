"""
languages
---------
Multi-language registry and abstraction for compiler toolchains.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from .base import Language, NotSupported, ToolchainNotFound, _scrub_paths, _to_jsonable
from .cpp import CppLanguage
from .c import CLanguage
from .python import PythonLanguage
from .java import JavaLanguage

_REGISTRY: Dict[str, Language] = {}


def register_language(lang: Language) -> None:
    _REGISTRY[lang.id.lower()] = lang


def get_language(lang_id: str) -> Optional[Language]:
    if not isinstance(lang_id, str):
        return None
    return _REGISTRY.get(lang_id.lower().strip())


def list_languages() -> List[Language]:
    return list(_REGISTRY.values())


# Register built-in languages
register_language(CppLanguage())
register_language(CLanguage())
register_language(PythonLanguage())
register_language(JavaLanguage())

__all__ = [
    "Language",
    "NotSupported",
    "ToolchainNotFound",
    "CppLanguage",
    "CLanguage",
    "PythonLanguage",
    "JavaLanguage",
    "register_language",
    "get_language",
    "list_languages",
    "_scrub_paths",
    "_to_jsonable",
]

