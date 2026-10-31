"""
java_rules.py
-------------
Auto-healer rules for Java compilation diagnostics:
1. "';' expected" -> append missing semicolon to statement.
2. Missing import (List, ArrayList, Scanner, Map, HashMap, Set, HashSet from java.util).
3. "cannot find symbol" with close misspelling (difflib identifier matching).
4. Missing return type in method declaration (e.g. 'public static add(...)' -> 'public static int add(...)').
5. 'string' vs 'String' (lowercase string type case fix).
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Optional, Set, Tuple

_JAVA_UTIL_TYPES = {
    "List": "java.util.List",
    "ArrayList": "java.util.ArrayList",
    "LinkedList": "java.util.LinkedList",
    "Map": "java.util.Map",
    "HashMap": "java.util.HashMap",
    "TreeMap": "java.util.TreeMap",
    "Set": "java.util.Set",
    "HashSet": "java.util.HashSet",
    "TreeSet": "java.util.TreeSet",
    "Scanner": "java.util.Scanner",
    "Collections": "java.util.Collections",
    "Arrays": "java.util.Arrays",
    "Queue": "java.util.Queue",
    "Deque": "java.util.Deque",
    "Iterator": "java.util.Iterator",
    "Optional": "java.util.Optional",
}


def _split_comment(line: str) -> Tuple[str, str]:
    """Split line into code portion and trailing single-line comment."""
    in_quote: Optional[str] = None
    escaped = False
    for i, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch in ("'", '"'):
            if in_quote == ch:
                in_quote = None
            elif in_quote is None:
                in_quote = ch
        elif ch == "/" and in_quote is None and i + 1 < len(line) and line[i + 1] == "/":
            return line[:i], line[i:]
    return line, ""


def fix_missing_semicolon(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix "';' expected" by appending a semicolon to the target statement.
    """
    line_no = error.get("line")
    lines = source.splitlines()
    if not lines:
        return None

    target_idx = -1
    candidates = []
    if line_no and 1 <= line_no <= len(lines):
        candidates.append(line_no - 1)
        if line_no - 2 >= 0:
            candidates.append(line_no - 2)
    else:
        candidates = list(range(len(lines)))

    for idx in candidates:
        code_part, _ = _split_comment(lines[idx])
        stripped = code_part.rstrip()
        if stripped and not stripped.endswith((";", "{", "}", ":", ",")):
            target_idx = idx
            break

    if target_idx == -1:
        return None

    code_part, comment = _split_comment(lines[target_idx])
    lines[target_idx] = code_part.rstrip() + ";" + (" " + comment if comment else "")
    patched = "\n".join(lines)
    return patched + ("\n" if source.endswith("\n") else "")


def fix_missing_import(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix missing java.util imports (List, ArrayList, Scanner, Map, etc.).
    """
    msg = error.get("message", "")
    raw = error.get("raw", "")
    text = f"{msg} {raw}"

    needed_types: List[str] = []
    for type_name, full_path in _JAVA_UTIL_TYPES.items():
        pattern = rf"\b(?:class|symbol:\s*class)?\s*{type_name}\b"
        if re.search(pattern, text) or f"class {type_name}" in text:
            needed_types.append(type_name)

    # If no specific type in message, scan source for common unimported java.util types
    if not needed_types:
        for type_name in _JAVA_UTIL_TYPES:
            if re.search(rf"\b{type_name}\b", source) and f"import java.util.{type_name}" not in source and "import java.util.*" not in source:
                needed_types.append(type_name)

    if not needed_types:
        return None

    # Determine import statement(s) to add
    if len(needed_types) > 1:
        imports_to_add = ["import java.util.*;"]
    else:
        imports_to_add = [f"import {_JAVA_UTIL_TYPES[t]};" for t in needed_types]

    lines = source.splitlines()
    # Find insertion point: after package declaration or existing imports
    insert_idx = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("package "):
            insert_idx = idx + 1
        elif stripped.startswith("import "):
            insert_idx = idx + 1

    new_lines = list(lines)
    for imp in reversed(imports_to_add):
        if imp not in source:
            new_lines.insert(insert_idx, imp)

    patched = "\n".join(new_lines)
    return patched + ("\n" if source.endswith("\n") else "")


def _collect_java_identifiers(source: str) -> Set[str]:
    """Extract candidate identifiers (variable names, method names, field names) from Java source."""
    candidates: Set[str] = set()
    # Match variable / method / parameter declarations:
    # e.g. int count = 10; String name; calculateTotal(...)
    decl_pattern = re.compile(r"\b(?:int|long|double|float|boolean|char|byte|short|String|[A-Z][A-Za-z0-9_]*)\s+([a-z][A-Za-z0-9_]*)\b")
    for m in decl_pattern.finditer(source):
        candidates.add(m.group(1))

    # Match method definitions:
    # e.g. public static int calculateTotal(...)
    method_pattern = re.compile(r"\b(?:public|private|protected|static|final|\s)*\s+[A-Za-z0-9_<>[\]]+\s+([a-z][A-Za-z0-9_]*)\s*\(")
    for m in method_pattern.finditer(source):
        candidates.add(m.group(1))

    return candidates


def fix_cannot_find_symbol_misspelling(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix 'cannot find symbol' caused by typo in variable or method name using difflib.
    """
    msg = error.get("message", "")
    raw = error.get("raw", "")
    line_no = error.get("line")
    text = f"{msg}\n{raw}"

    # Extract symbol name: e.g. "symbol:   variable cont" or "symbol:   method calculteTotal"
    sym_match = re.search(r"symbol:\s*(?:variable|method|class)\s+([A-Za-z0-9_]+)", text)
    bad_symbol = sym_match.group(1) if sym_match else None

    lines = source.splitlines()
    if not lines:
        return None

    if not bad_symbol and line_no and 1 <= line_no <= len(lines):
        # Look for identifiers on that line
        words = re.findall(r"\b[a-z][A-Za-z0-9_]*\b", lines[line_no - 1])
        if words:
            bad_symbol = words[-1]

    if not bad_symbol:
        return None

    candidates = _collect_java_identifiers(source)
    candidates.discard(bad_symbol)
    matches = difflib.get_close_matches(bad_symbol, list(candidates), n=1, cutoff=0.5)
    if not matches:
        return None

    replacement = matches[0]
    target_pattern = re.compile(rf"\b{re.escape(bad_symbol)}\b")

    if line_no and 1 <= line_no <= len(lines):
        line = lines[line_no - 1]
        if target_pattern.search(line):
            lines[line_no - 1] = target_pattern.sub(replacement, line)
            patched = "\n".join(lines)
            return patched + ("\n" if source.endswith("\n") else "")

    for idx, line in enumerate(lines):
        if target_pattern.search(line):
            lines[idx] = target_pattern.sub(replacement, line)
            patched = "\n".join(lines)
            return patched + ("\n" if source.endswith("\n") else "")

    return None


def fix_missing_return_type(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix 'invalid method declaration; return type required' by inserting the return type.
    Infers int, String, boolean, double or void based on returned expressions in the method.
    """
    line_no = error.get("line")
    lines = source.splitlines()
    if not lines or line_no is None or not (1 <= line_no <= len(lines)):
        return None

    target_idx = line_no - 1
    line = lines[target_idx]

    # Pattern: [modifiers] methodName(args)
    # e.g. public static add(int a, int b) {
    m = re.search(r"^(\s*(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*)([a-z][A-Za-z0-9_]*)\s*\(", line)
    if not m:
        return None

    modifiers_part, method_name = m.group(1), m.group(2)

    # Infer return type from method body
    inferred_type = "void"
    body_lines = lines[target_idx:target_idx + 25]
    body_text = "\n".join(body_lines)
    ret_match = re.search(r"\breturn\s+([^;]+);", body_text)
    if ret_match:
        ret_expr = ret_match.group(1).strip()
        if re.search(r'^[0-9]+$', ret_expr) or re.search(r'\b[a-z][A-Za-z0-9_]*\s*[\+\-\*/%]\s*[a-z0-9_]+', ret_expr):
            inferred_type = "int"
        elif ret_expr.startswith('"') and ret_expr.endswith('"'):
            inferred_type = "String"
        elif ret_expr in ("true", "false"):
            inferred_type = "boolean"
        elif re.search(r'^[0-9]+\.[0-9]+', ret_expr):
            inferred_type = "double"
        else:
            inferred_type = "int"

    # Insert inferred return type before method name
    new_line = line[:len(modifiers_part)] + inferred_type + " " + line[len(modifiers_part):]
    lines[target_idx] = new_line
    patched = "\n".join(lines)
    return patched + ("\n" if source.endswith("\n") else "")


def fix_string_type_case(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix lowercase 'string' to Java 'String'.
    """
    # Replace all occurrences of whole word 'string' followed by whitespace, bracket or variable name
    patched = re.sub(r"\bstring\b(?=\s*\[|\s+[A-Za-z0-9_]+)", "String", source)
    if patched == source:
        patched = re.sub(r"\bstring\b", "String", source)
    if patched != source:
        return patched
    return None


def attempt_fix_java(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Main dispatcher for Java rules.
    Takes source code and a diagnostic dict, returns patched source or None.
    """
    msg = error.get("message", "").lower()
    raw = error.get("raw", "").lower()
    text = f"{msg} {raw}"

    # 1. Missing semicolon
    if "';' expected" in text or "expected ';'" in text or "semicolon" in text:
        res = fix_missing_semicolon(source, error)
        if res and res != source:
            return res

    # 2. Lowercase string
    if "class string" in text or re.search(r"\bstring\b", text):
        res = fix_string_type_case(source, error)
        if res and res != source:
            return res

    # 3. Missing return type
    if "return type required" in text or "invalid method declaration" in text:
        res = fix_missing_return_type(source, error)
        if res and res != source:
            return res

    # 4. Missing import (java.util)
    if any(t.lower() in text for t in _JAVA_UTIL_TYPES):
        res = fix_missing_import(source, error)
        if res and res != source:
            return res

    # 5. Cannot find symbol typo
    if "cannot find symbol" in text or "symbol" in text:
        res = fix_cannot_find_symbol_misspelling(source, error)
        if res and res != source:
            return res

    # General fallback sequence
    rules = [
        fix_missing_semicolon,
        fix_string_type_case,
        fix_missing_return_type,
        fix_missing_import,
        fix_cannot_find_symbol_misspelling,
    ]
    for rule in rules:
        try:
            res = rule(source, error)
            if res is not None and res != source:
                return res
        except Exception:
            continue

    return None

