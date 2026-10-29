"""
phase_explainer.py
------------------
Plain-English compiler pipeline explainer for MiniC programs.
Given the source code, token stream, AST, symbol table, and IR,
produces a structured, plain-English breakdown of what each phase did.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.ast_nodes import Program, pretty_print_ast
from core.ir import Instruction, generate_ir
from core.lexer import Lexer, Token
from core.parser import Parser
from core.semantic import SemanticAnalyzer, SymbolTable
from ai.llm_client import LLMClient
from ai.schema_utils import query_structured_json


PHASE_EXPLAINER_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "program_summary": {"type": "string"},
        "phases": {
            "type": "object",
            "properties": {
                "lexical_analysis": {
                    "type": "object",
                    "properties": {
                        "token_count": {"type": "integer"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["token_count", "explanation"],
                },
                "syntax_analysis": {
                    "type": "object",
                    "properties": {
                        "ast_summary": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["ast_summary", "explanation"],
                },
                "semantic_analysis": {
                    "type": "object",
                    "properties": {
                        "symbols_declared": {"type": "array", "items": {"type": "string"}},
                        "explanation": {"type": "string"},
                    },
                    "required": ["symbols_declared", "explanation"],
                },
                "ir_generation": {
                    "type": "object",
                    "properties": {
                        "instruction_count": {"type": "integer"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["instruction_count", "explanation"],
                },
            },
            "required": [
                "lexical_analysis",
                "syntax_analysis",
                "semantic_analysis",
                "ir_generation",
            ],
        },
    },
    "required": ["program_summary", "phases"],
}


def create_fallback_explanation(
    source_code: str,
    tokens: List[Token],
    ast: Program,
    symbol_table: SymbolTable,
    ir: List[Instruction],
) -> Dict[str, Any]:
    """Deterministic fallback explanation generated directly from compiler artifacts."""
    symbol_names = [f"{sym.name}" for sym in symbol_table.symbols.values()]
    decl_types = [decl.__class__.__name__ for decl in ast.declarations]

    return {
        "program_summary": f"MiniC program with {len(ast.declarations)} top-level declaration(s).",
        "phases": {
            "lexical_analysis": {
                "token_count": len(tokens),
                "explanation": (
                    f"Lexical analysis scanned the source characters and produced {len(tokens)} tokens, "
                    f"categorizing keywords, identifiers, operators, and literals while stripping comments."
                ),
            },
            "syntax_analysis": {
                "ast_summary": f"Program AST containing: {', '.join(decl_types) or 'empty'}.",
                "explanation": (
                    f"Recursive-descent parser verified grammar productions according to operator precedence "
                    f"and structured statements into an Abstract Syntax Tree with {len(ast.declarations)} declaration(s)."
                ),
            },
            "semantic_analysis": {
                "symbols_declared": symbol_names,
                "explanation": (
                    f"Semantic analyzer populated the scoped symbol table with {len(symbol_names)} symbol(s) "
                    f"and confirmed type safety, variable initialization, return statements, and call signatures."
                ),
            },
            "ir_generation": {
                "instruction_count": len(ir),
                "explanation": (
                    f"Intermediate Representation generation flattened expressions and control flow into "
                    f"{len(ir)} Three-Address Code (TAC) quadruples with explicit temporary and label management."
                ),
            },
        },
    }


def explain_phases(
    source_code: str,
    tokens: List[Token],
    ast: Program,
    symbol_table: SymbolTable,
    ir: List[Instruction],
    client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    """
    Generate a plain-English explanation of what each compiler phase did for the given program.
    Returns structured JSON validated against PHASE_EXPLAINER_SCHEMA.
    """
    llm = client or LLMClient()

    # If in mock mode, register a valid schema response if not already registered
    if getattr(llm, "mock_mode", False) and hasattr(llm.provider, "register_response"):
        if "EXPLAIN_COMPILER_PHASES" not in getattr(llm.provider, "canned_responses", {}):
            mock_resp = (
                '{\n'
                '  "program_summary": "Calculates values and prints results in MiniC.",\n'
                '  "phases": {\n'
                '    "lexical_analysis": {\n'
                f'      "token_count": {len(tokens)},\n'
                '      "explanation": "Tokenized input stream into keywords, identifiers, and literals."\n'
                '    },\n'
                '    "syntax_analysis": {\n'
                '      "ast_summary": "Built AST with FunctionDef and Block expressions.",\n'
                '      "explanation": "Parsed tokens using recursive-descent precedence rules."\n'
                '    },\n'
                '    "semantic_analysis": {\n'
                f'      "symbols_declared": {[k for k in symbol_table.symbols.keys()]},\n'
                '      "explanation": "Verified scopes, type correctness, and variable initialization."\n'
                '    },\n'
                '    "ir_generation": {\n'
                f'      "instruction_count": {len(ir)},\n'
                '      "explanation": "Lowered AST into Three-Address Code quadruples."\n'
                '    }\n'
                '  }\n'
                '}'
            )
            llm.provider.register_response("EXPLAIN_COMPILER_PHASES", mock_resp)

    system_prompt = (
        "You are an expert compiler engineer explaining the phases of a compiler to a developer.\n"
        "Analyze the provided MiniC program and the artifacts generated at each compilation phase "
        "(Lexer, Parser, Semantic Analysis, and Three-Address Code IR).\n"
        "Explain in plain, clear English what each phase did for this specific program."
    )

    token_preview = ", ".join(t.type.name for t in tokens[:20]) + ("..." if len(tokens) > 20 else "")
    ast_pretty = pretty_print_ast(ast)[:800]
    ir_text = "\n".join(str(i) for i in ir[:20])

    user_prompt = (
        f"EXPLAIN_COMPILER_PHASES\n\n"
        f"### 1. SOURCE CODE:\n{source_code}\n\n"
        f"### 2. LEXICAL ANALYSIS (Tokens: {len(tokens)}):\n{token_preview}\n\n"
        f"### 3. SYNTAX ANALYSIS (AST):\n{ast_pretty}\n\n"
        f"### 4. SEMANTIC ANALYSIS (Symbols: {list(symbol_table.symbols.keys())}):\n"
        f"{', '.join(f'{k}: {type(v).__name__}' for k, v in symbol_table.symbols.items())}\n\n"
        f"### 5. IR GENERATION (TAC Instructions: {len(ir)}):\n{ir_text}\n"
    )

    fallback = lambda: create_fallback_explanation(source_code, tokens, ast, symbol_table, ir)

    return query_structured_json(
        client=llm,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=PHASE_EXPLAINER_SCHEMA,
        fallback_factory=fallback,
    )


def explain_compilation(
    source_code: str,
    client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    """
    Convenience end-to-end entry point: compiles source code through all phases
    and returns the structured explanation.
    """
    lexer = Lexer(source_code)
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)
    symbol_table = analyzer.global_scope

    ir = generate_ir(ast)

    return explain_phases(source_code, tokens, ast, symbol_table, ir, client=client)
