"""
bug_detector.py
---------------
AI-driven logic bug detector for MiniC programs.

Identifies potential logic bugs (off-by-one errors, infinite loops, unreachable code)
using the LLM, and strictly enforces ground-truth AST validation:
any finding that does NOT cite a real line number present in the AST is discarded.

Validates structured JSON against a schema, retries once on error, and falls back gracefully.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set

from core.ast_nodes import ASTNode, Program, pretty_print_ast
from core.lexer import Lexer
from core.parser import Parser
from ai.llm_client import LLMClient
from ai.schema_utils import query_structured_json


# ── JSON Schema ───────────────────────────────────────────────────────────────

BUG_DETECTOR_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "bugs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line": {"type": "integer"},
                    "category": {
                        "type": "string",
                        "enum": ["off_by_one", "infinite_loop", "unreachable_code", "other"],
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "warning"],
                    },
                    "description": {"type": "string"},
                    "fix_suggestion": {"type": "string"},
                },
                "required": ["line", "category", "severity", "description"],
            },
        },
    },
    "required": ["summary", "bugs"],
}


# ── AST Line Number Collection ────────────────────────────────────────────────

def collect_ast_lines(node: Any) -> Set[int]:
    """
    Recursively collects all positive line numbers explicitly referenced
    in the AST nodes.
    """
    lines: Set[int] = set()
    if not isinstance(node, ASTNode):
        return lines

    line_val = getattr(node, "line", 0)
    if isinstance(line_val, int) and line_val > 0:
        lines.add(line_val)

    for _, val in vars(node).items():
        if isinstance(val, ASTNode):
            lines.update(collect_ast_lines(val))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, ASTNode):
                    lines.update(collect_ast_lines(item))

    return lines


# ── Core Bug Detector ─────────────────────────────────────────────────────────

def detect_bugs(
    source_code: str,
    ast: Optional[Program] = None,
    client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    """
    Detect likely logic bugs (off-by-one, infinite loops, unreachable code)
    in the provided MiniC program.

    Strictly keeps only findings that cite a real line number in the AST.
    """
    # Parse source code to AST if not supplied
    if ast is None:
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

    # Collect ground-truth AST line numbers
    ast_lines = collect_ast_lines(ast)

    llm = client or LLMClient()

    # Register default mock response for offline / mock testing if in mock mode
    if getattr(llm, "mock_mode", False) and hasattr(llm.provider, "register_response"):
        if "DETECT_LOGIC_BUGS" not in getattr(llm.provider, "canned_responses", {}):
            # Select first valid AST line for a realistic canned finding
            sample_line = min(ast_lines) if ast_lines else 1
            mock_resp = (
                '{\n'
                '  "summary": "Mock analysis: Potential loop boundary logic issue detected.",\n'
                '  "bugs": [\n'
                '    {\n'
                f'      "line": {sample_line},\n'
                '      "category": "off_by_one",\n'
                '      "severity": "medium",\n'
                '      "description": "Potential boundary condition offset at loop condition.",\n'
                '      "fix_suggestion": "Review comparison operator (< vs <=)."\n'
                '    }\n'
                '  ]\n'
                '}'
            )
            llm.provider.register_response("DETECT_LOGIC_BUGS", mock_resp)

    # Format source code with line numbers for prompt clarity
    source_lines = [
        f"{idx + 1:3d} | {line}"
        for idx, line in enumerate(source_code.splitlines())
    ]
    numbered_source = "\n".join(source_lines)
    ast_pretty = pretty_print_ast(ast)[:1000]

    system_prompt = (
        "You are an expert static analyzer and software security auditor specializing in MiniC.\n"
        "Analyze the provided program for subtle logic bugs:\n"
        "  1. off_by_one: Loop bounds using '<' instead of '<=' or index offsets.\n"
        "  2. infinite_loop: Loops with missing update steps or invariant loop conditions.\n"
        "  3. unreachable_code: Statements following return or dead branches.\n"
        "  4. other: Uninitialized variable reads or logical deadlocks.\n\n"
        "CRITICAL RULE:\n"
        "You MUST specify the EXACT 1-based source code line number where each bug occurs.\n"
        "An automated AST validator will verify every cited line number against the parsed AST; "
        "any hallucinated or non-existent line numbers will be discarded immediately."
    )

    user_prompt = (
        f"DETECT_LOGIC_BUGS\n\n"
        f"### 1. Source Code (with Line Numbers):\n{numbered_source}\n\n"
        f"### 2. Valid AST Lines:\n{sorted(list(ast_lines))}\n\n"
        f"### 3. Abstract Syntax Tree (AST):\n{ast_pretty}\n\n"
        f"Identify any likely logic bugs and return them strictly conforming to the JSON schema."
    )

    fallback = lambda: {
        "summary": "Graceful fallback: Static bug analysis could not be completed.",
        "bugs": [],
    }

    raw_data = query_structured_json(
        client=llm,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=BUG_DETECTOR_SCHEMA,
        fallback_factory=fallback,
    )

    all_bugs = raw_data.get("bugs", [])
    valid_bugs: List[Dict[str, Any]] = []
    discarded_bugs: List[Dict[str, Any]] = []

    for bug in all_bugs:
        line_num = bug.get("line")
        if isinstance(line_num, int) and line_num in ast_lines:
            valid_bugs.append(bug)
        else:
            discarded_bugs.append({
                "bug": bug,
                "reason": (
                    f"Line {line_num} does not exist in AST line set: "
                    f"{sorted(list(ast_lines))}"
                ),
            })

    return {
        "summary": raw_data.get("summary", ""),
        "bugs": valid_bugs,
        "discarded_bugs": discarded_bugs,
        "valid_ast_lines": sorted(list(ast_lines)),
        "raw_bug_count": len(all_bugs),
        "valid_bug_count": len(valid_bugs),
        "discarded_bug_count": len(discarded_bugs),
    }
