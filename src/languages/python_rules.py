"""
python_rules.py
---------------
Auto-healer rules for Python syntax and runtime diagnostics:
1. Missing colon after if/elif/else/for/while/def/class/try/except/finally/with.
2. Unmatched (, [, {.
3. Bad indentation (expected an indented block, unexpected indent).
4. "print x" -> print(x) (Python 2 to 3 migration).
5. '=' vs '==' in conditions (if x = 5: -> if x == 5:).
6. Undefined name from a close misspelling (difflib matching against defined symbols).
"""

from __future__ import annotations

import ast
import difflib
import re
from typing import Any, Dict, List, Optional, Set, Tuple

_COLON_KEYWORDS = (
    "if", "elif", "else", "for", "while", "def", "class",
    "try", "except", "finally", "with", "match", "case",
    "async def", "async for", "async with",
)

_COLON_KEYWORD_RE = re.compile(
    r"^\s*(?:async\s+)?(if|elif|else|for|while|def|class|try|except|finally|with|match|case)\b"
)


def _split_comment(line: str) -> Tuple[str, str]:
    """Split line into code portion and trailing comment."""
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
        elif ch == "#" and in_quote is None:
            return line[:i], line[i:]
    return line, ""


def fix_missing_colon(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Append missing colon after if/elif/else/for/while/def/class/try/etc.
    """
    line_no = error.get("line")
    lines = source.splitlines()
    if not lines:
        return None

    # Line number reported by Python can be 1-indexed, sometimes pointing to the next line
    target_idx = -1
    candidates = []
    if line_no is not None and 1 <= line_no <= len(lines):
        candidates.append(line_no - 1)
        if line_no - 2 >= 0:
            candidates.append(line_no - 2)
    else:
        candidates = list(range(len(lines)))

    for idx in candidates:
        code_part, comment = _split_comment(lines[idx])
        stripped = code_part.rstrip()
        if _COLON_KEYWORD_RE.match(stripped) and not stripped.endswith(":"):
            target_idx = idx
            break

    if target_idx == -1:
        # Search anywhere in file
        for idx, line in enumerate(lines):
            code_part, comment = _split_comment(line)
            stripped = code_part.rstrip()
            if _COLON_KEYWORD_RE.match(stripped) and not stripped.endswith(":"):
                target_idx = idx
                break

    if target_idx == -1:
        return None

    code_part, comment = _split_comment(lines[target_idx])
    lines[target_idx] = code_part.rstrip() + ":" + (" " + comment if comment else "")
    patched = "\n".join(lines)
    if source.endswith("\n") and not patched.endswith("\n"):
        patched += "\n"
    return patched


def fix_unmatched_brackets(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix unmatched (, [, { by closing unclosed brackets or removing stray closers.
    """
    msg = error.get("message", "")
    line_no = error.get("line")
    lines = source.splitlines()
    if not lines:
        return None

    target_idx = (line_no - 1) if (line_no and 1 <= line_no <= len(lines)) else 0

    # Case 1: Specific bracket unclosed message
    # e.g. "'(' was never closed", "'[' was never closed", "'{' was never closed"
    closing_pair = {"(": ")", "[": "]", "{": "}"}
    for op, cl in closing_pair.items():
        if f"'{op}' was never closed" in msg or f"unclosed '{op}'" in msg:
            code_part, comment = _split_comment(lines[target_idx])
            lines[target_idx] = code_part.rstrip() + cl + (" " + comment if comment else "")
            patched = "\n".join(lines)
            return patched + ("\n" if source.endswith("\n") else "")

    # Case 2: Stray closing bracket, e.g. "unmatched ')'"
    for cl in (")", "]", "}"):
        if f"unmatched '{cl}'" in msg:
            col = error.get("column")
            line_str = lines[target_idx]
            if col and 1 <= col <= len(line_str) and line_str[col - 1] == cl:
                lines[target_idx] = line_str[:col - 1] + line_str[col:]
            else:
                pos = line_str.rfind(cl)
                if pos != -1:
                    lines[target_idx] = line_str[:pos] + line_str[pos + 1:]
            patched = "\n".join(lines)
            return patched + ("\n" if source.endswith("\n") else "")

    # Case 3: Bracket counting on target line
    code_part, comment = _split_comment(lines[target_idx])
    counts = {"(": 0, "[": 0, "{": 0}
    in_quote: Optional[str] = None
    escaped = False
    for ch in code_part:
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
            continue
        if in_quote:
            continue
        if ch == "(":
            counts["("] += 1
        elif ch == ")":
            counts["("] = max(0, counts["("] - 1)
        elif ch == "[":
            counts["["] += 1
        elif ch == "]":
            counts["["] = max(0, counts["["] - 1)
        elif ch == "{":
            counts["{"] += 1
        elif ch == "}":
            counts["{"] = max(0, counts["{"] - 1)

    additions = ""
    if counts["{"] > 0:
        additions += "}" * counts["{"]
    if counts["["] > 0:
        additions += "]" * counts["["]
    if counts["("] > 0:
        additions += ")" * counts["("]

    if additions:
        lines[target_idx] = code_part.rstrip() + additions + (" " + comment if comment else "")
        patched = "\n".join(lines)
        return patched + ("\n" if source.endswith("\n") else "")

    return None


def fix_bad_indentation(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix indentation errors:
    - "expected an indented block" -> indent line(s) by 4 spaces.
    - "unexpected indent" -> dedent line to match previous statement.
    """
    msg = error.get("message", "").lower()
    line_no = error.get("line")
    lines = source.splitlines()
    if not lines or line_no is None or not (1 <= line_no <= len(lines)):
        return None

    target_idx = line_no - 1

    if "expected an indented block" in msg:
        # Find the indentation of the preceding block header (line before or earlier)
        header_idx = target_idx - 1
        while header_idx >= 0 and not lines[header_idx].strip():
            header_idx -= 1
        header_indent = 0
        if header_idx >= 0:
            header_line = lines[header_idx]
            header_indent = len(header_line) - len(header_line.lstrip(" "))
        new_indent = header_indent + 4

        # Indent lines in this block (until empty line, EOF, or next outer statement)
        curr = target_idx
        while curr < len(lines):
            line = lines[curr]
            if not line.strip():
                curr += 1
                continue
            curr_indent = len(line) - len(line.lstrip(" "))
            if curr > target_idx and (curr_indent > 0 or _COLON_KEYWORD_RE.match(line.strip())):
                # If subsequent lines already had indent or started a new top-level construct, stop
                if line.strip().startswith(("def ", "class ", "if __name__")):
                    break
            lines[curr] = (" " * new_indent) + line.lstrip(" ")
            curr += 1

        patched = "\n".join(lines)
        return patched + ("\n" if source.endswith("\n") else "")

    if "unexpected indent" in msg or "unindent does not match" in msg:
        # Dedent target line to match previous non-empty line
        prev_idx = target_idx - 1
        while prev_idx >= 0 and not lines[prev_idx].strip():
            prev_idx -= 1
        prev_indent = 0
        if prev_idx >= 0:
            prev_line = lines[prev_idx]
            prev_indent = len(prev_line) - len(prev_line.lstrip(" "))
        lines[target_idx] = (" " * prev_indent) + lines[target_idx].lstrip(" ")
        patched = "\n".join(lines)
        return patched + ("\n" if source.endswith("\n") else "")

    return None


def fix_print_statement(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix Python 2 'print x' statement to Python 3 'print(x)'.
    """
    line_no = error.get("line")
    lines = source.splitlines()
    if not lines:
        return None

    candidates = []
    if line_no and 1 <= line_no <= len(lines):
        candidates.append(line_no - 1)
    candidates.extend(range(len(lines)))

    target_idx = -1
    print_re = re.compile(r"^(\s*)print\s+(?![\(=])(.+)$")
    for idx in candidates:
        code_part, _ = _split_comment(lines[idx])
        if print_re.match(code_part):
            target_idx = idx
            break

    if target_idx == -1:
        return None

    line = lines[target_idx]
    code_part, comment = _split_comment(line)
    m = print_re.match(code_part)
    if not m:
        return None

    indent, rest = m.group(1), m.group(2).rstrip()
    lines[target_idx] = f"{indent}print({rest})" + (" " + comment if comment else "")
    patched = "\n".join(lines)
    return patched + ("\n" if source.endswith("\n") else "")


def fix_assignment_in_condition(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix single '=' used instead of '==' in if/elif/while conditions.
    """
    line_no = error.get("line")
    lines = source.splitlines()
    if not lines:
        return None

    candidates = []
    if line_no and 1 <= line_no <= len(lines):
        candidates.append(line_no - 1)
    candidates.extend(range(len(lines)))

    cond_re = re.compile(r"^(\s*(?:if|elif|while)\b\s+)(.*)$")
    target_idx = -1
    for idx in candidates:
        code_part, _ = _split_comment(lines[idx])
        if cond_re.match(code_part) and re.search(r"(?<![!<>=:])=(?![=])", code_part):
            target_idx = idx
            break

    if target_idx == -1:
        return None

    line = lines[target_idx]
    code_part, comment = _split_comment(line)
    # Replace single '=' with '=='
    new_code = re.sub(r"(?<![!<>=:])=(?![=])", "==", code_part)
    lines[target_idx] = new_code + comment
    patched = "\n".join(lines)
    return patched + ("\n" if source.endswith("\n") else "")


def _collect_identifier_candidates(source: str) -> Set[str]:
    """Extract all candidate identifiers defined in source code and common builtins."""
    import builtins
    candidates: Set[str] = set(dir(builtins))
    # Extract identifiers from regex
    for name in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", source):
        candidates.add(name)
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                candidates.add(node.name)
            elif isinstance(node, ast.arg):
                candidates.add(node.arg)
            elif isinstance(node, ast.Name):
                candidates.add(node.id)
    except Exception:
        pass
    return candidates


def fix_undefined_name_typo(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Fix undefined name / NameError using difflib matching or Python 3.10+ suggestions.
    """
    msg = error.get("message", "")
    line_no = error.get("line")
    lines = source.splitlines()
    if not lines:
        return None

    bad_name: Optional[str] = None
    replacement: Optional[str] = None

    # Check for direct suggestion: "Did you mean: 'foo'?"
    sugg_m = re.search(r"Did you mean: '([A-Za-z0-9_]+)'\?", msg)
    if sugg_m:
        replacement = sugg_m.group(1)

    # Check for undefined name: "name 'foo' is not defined" or "undefined name 'foo'"
    name_m = re.search(r"name '([A-Za-z0-9_]+)' is not defined", msg) or re.search(r"undefined name '([A-Za-z0-9_]+)'", msg)
    if name_m:
        bad_name = name_m.group(1)

    if not bad_name and line_no and 1 <= line_no <= len(lines):
        # Look for identifiers on that line that might be close to defined identifiers
        words = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", lines[line_no - 1])
        if words:
            bad_name = words[-1]

    if not bad_name:
        return None

    if not replacement:
        candidates = _collect_identifier_candidates(source)
        # Remove bad_name itself
        candidates.discard(bad_name)
        matches = difflib.get_close_matches(bad_name, list(candidates), n=1, cutoff=0.5)
        if matches:
            replacement = matches[0]

    if not replacement or replacement == bad_name:
        return None

    # Replace on the target line, or everywhere in the source if line is missing
    target_pattern = re.compile(rf"\b{re.escape(bad_name)}\b")
    if line_no and 1 <= line_no <= len(lines):
        line = lines[line_no - 1]
        if target_pattern.search(line):
            lines[line_no - 1] = target_pattern.sub(replacement, line)
            patched = "\n".join(lines)
            return patched + ("\n" if source.endswith("\n") else "")

    # Fallback: replace on first matching line
    for idx, line in enumerate(lines):
        if target_pattern.search(line):
            lines[idx] = target_pattern.sub(replacement, line)
            patched = "\n".join(lines)
            return patched + ("\n" if source.endswith("\n") else "")

    return None


def attempt_fix_python(source: str, error: Dict[str, Any]) -> Optional[str]:
    """
    Main dispatcher for Python rules.
    Takes source code and a diagnostic dict, returns patched source or None.
    """
    category = error.get("category", "")
    msg = error.get("message", "").lower()

    # Rule dispatch order based on diagnostic category / contents
    if category == "indentation_error" or "indent" in msg or "tab" in msg:
        res = fix_bad_indentation(source, error)
        if res and res != source:
            return res

    if "print" in msg or "missing parentheses in call to 'print'" in msg:
        res = fix_print_statement(source, error)
        if res and res != source:
            return res

    if category == "name_error" or "is not defined" in msg or "undefined name" in msg:
        res = fix_undefined_name_typo(source, error)
        if res and res != source:
            return res

    if "maybe you meant '=='" in msg or "=" in msg and ("invalid syntax" in msg or "cannot assign" in msg):
        res = fix_assignment_in_condition(source, error)
        if res and res != source:
            return res

    if "expected ':'" in msg or "colon" in msg:
        res = fix_missing_colon(source, error)
        if res and res != source:
            return res

    if "never closed" in msg or "unclosed" in msg or "unmatched" in msg or any(b in msg for b in ("(", "[", "{", ")", "]", "}")):
        res = fix_unmatched_brackets(source, error)
        if res and res != source:
            return res

    # General fallback sequence for syntax errors
    rules = [
        fix_missing_colon,
        fix_assignment_in_condition,
        fix_print_statement,
        fix_unmatched_brackets,
        fix_bad_indentation,
        fix_undefined_name_typo,
    ]
    for rule in rules:
        try:
            res = rule(source, error)
            if res is not None and res != source:
                return res
        except Exception:
            continue

    return None

