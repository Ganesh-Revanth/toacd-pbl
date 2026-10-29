"""
ai_optimizer.py
---------------
AI-driven Intermediate Representation (TAC) Optimizer.

Sends Three-Address Code to the LLM for optimization suggestions as structured JSON.
Crucially: applies a suggestion ONLY IF the TAC interpreter produces identical output
before and after optimization (equivalence check).
Logs accepted and rejected suggestions with rationale.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.ast_nodes import Program
from core.ir import Const, Instruction, Operand, generate_ir
from core.interpreter import Interpreter
from core.lexer import Lexer
from core.parser import Parser
from core.semantic import SemanticAnalyzer
from ai.llm_client import LLMClient
from ai.schema_utils import query_structured_json


# ── JSON Schema ───────────────────────────────────────────────────────────────

AI_OPTIMIZER_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "analysis": {"type": "string"},
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "suggestion_id": {"type": "string"},
                    "description": {"type": "string"},
                    "transformation_type": {"type": "string"},
                    "target_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "replacement_instructions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {"type": "string"},
                                "result": {"type": ["string", "null"]},
                                "arg1": {"type": ["string", "number", "boolean", "null", "object"]},
                                "arg2": {"type": ["string", "number", "boolean", "null", "object"]},
                            },
                            "required": ["op"],
                        },
                    },
                },
                "required": [
                    "suggestion_id",
                    "description",
                    "target_indices",
                    "replacement_instructions",
                ],
            },
        },
    },
    "required": ["suggestions"],
}


# ── Instruction Serialization & Parsing ───────────────────────────────────────

def instruction_to_dict(inst: Instruction) -> Dict[str, Any]:
    """Serialize an Instruction into a JSON-friendly dictionary."""
    def format_operand(op: Optional[Operand]) -> Any:
        if op is None:
            return None
        if isinstance(op, Const):
            return op.value
        return op

    return {
        "op": inst.op,
        "result": inst.result,
        "arg1": format_operand(inst.arg1),
        "arg2": format_operand(inst.arg2),
        "text": str(inst),
    }


def parse_operand(val: Any) -> Optional[Operand]:
    """Parse a JSON value back into an Instruction Operand (Const or str)."""
    if val is None:
        return None
    if isinstance(val, (int, float, bool)):
        return Const(val)
    if isinstance(val, dict) and "value" in val:
        return Const(val["value"])
    if isinstance(val, str):
        # Boolean string literals
        if val.lower() == "true":
            return Const(True)
        if val.lower() == "false":
            return Const(False)
        # Quoted strings
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            return Const(val[1:-1])
        # Numeric string literals
        try:
            if "." in val:
                return Const(float(val))
            return Const(int(val))
        except ValueError:
            pass
        return val
    if isinstance(val, list):
        # e.g., parameter names in FUNC_BEGIN
        return val
    return val


def dict_to_instruction(d: Dict[str, Any]) -> Instruction:
    """Deserialize a dictionary into a TAC Instruction."""
    op = str(d["op"])
    result = str(d["result"]) if d.get("result") is not None else None
    arg1 = parse_operand(d.get("arg1"))
    arg2 = parse_operand(d.get("arg2"))
    return Instruction(op=op, result=result, arg1=arg1, arg2=arg2)


# ── Suggestion Application & Verification ────────────────────────────────────

def apply_suggestion_patch(
    current_ir: List[Instruction],
    target_indices: List[int],
    replacement_insts: List[Instruction],
) -> List[Instruction]:
    """
    Apply a replacement patch to current_ir:
    Replaces the instructions at target_indices with replacement_insts.
    If target_indices is empty, appends replacement_insts.
    """
    if not target_indices:
        return current_ir + replacement_insts

    target_set = set(target_indices)
    first_idx = min(target_set)

    candidate_ir: List[Instruction] = []
    for idx, inst in enumerate(current_ir):
        if idx == first_idx:
            candidate_ir.extend(replacement_insts)
        if idx not in target_set:
            candidate_ir.append(inst)

    return candidate_ir


def run_safely(instructions: List[Instruction], max_steps: int = 200000) -> Tuple[bool, List[str], str]:
    """
    Execute instructions in the TAC interpreter safely.
    Returns (success: bool, output: List[str], error_message: str).
    """
    try:
        interpreter = Interpreter(instructions)
        output = interpreter.run(max_steps=max_steps)
        return True, output, ""
    except Exception as exc:
        return False, [], str(exc)


# ── Core AI Optimizer ─────────────────────────────────────────────────────────

def ai_optimize_ir(
    ir: List[Instruction],
    client: Optional[LLMClient] = None,
    max_suggestions: int = 10,
) -> Dict[str, Any]:
    """
    Send the IR to the LLM for optimization suggestions as structured JSON.
    Applies each suggestion ONLY IF the interpreter produces identical output before and after.
    Logs accepted and rejected suggestions.
    """
    llm = client or LLMClient()

    # Baseline execution to obtain expected observable output oracle
    base_ok, base_output, base_err = run_safely(ir)
    if not base_ok:
        return {
            "analysis": f"Baseline execution failed ({base_err}); AI optimization aborted.",
            "initial_ir": ir,
            "optimized_ir": list(ir),
            "accepted_suggestions": [],
            "rejected_suggestions": [
                {
                    "suggestion_id": "init",
                    "description": "Baseline IR failed execution",
                    "reason": base_err,
                }
            ],
            "initial_instruction_count": len(ir),
            "final_instruction_count": len(ir),
            "equivalence_verified": False,
        }

    # Register default mock response for offline / mock testing if in mock mode
    if getattr(llm, "mock_mode", False) and hasattr(llm.provider, "register_response"):
        if "OPTIMIZE_TAC_IR" not in getattr(llm.provider, "canned_responses", {}):
            mock_resp = (
                '{\n'
                '  "analysis": "Identified opportunities for strength reduction and dead code elimination.",\n'
                '  "suggestions": []\n'
                '}'
            )
            llm.provider.register_response("OPTIMIZE_TAC_IR", mock_resp)

    # Format IR for LLM prompt
    ir_lines = [f"{idx:3d}: {inst}" for idx, inst in enumerate(ir)]
    ir_text = "\n".join(ir_lines)

    system_prompt = (
        "You are an expert compiler optimization engineer.\n"
        "Your task is to analyze Three-Address Code (TAC) and suggest performance optimizations.\n"
        "Valid optimizations include: strength reduction, dead instruction elimination, "
        "redundant move elimination, constant folding, and algebraic simplifications.\n"
        "CRITICAL REQUIREMENT:\n"
        "The program output MUST remain 100% identical. An automated interpreter will execute "
        "the code before and after your proposed changes; any discrepancy causes immediate rejection.\n"
        "Specify each suggestion with target_indices (0-based list of instruction indices being replaced) "
        "and replacement_instructions (array of new instruction objects to insert in their place)."
    )

    user_prompt = (
        f"OPTIMIZE_TAC_IR\n\n"
        f"Current TAC Instructions (Total: {len(ir)}):\n"
        f"{ir_text}\n\n"
        f"Observable Baseline Output:\n"
        f"{base_output}\n\n"
        f"Please provide optimization suggestions as structured JSON."
    )

    fallback = lambda: {
        "analysis": "Fallback: No AI optimizations proposed due to response failure.",
        "suggestions": [],
    }

    response_data = query_structured_json(
        client=llm,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=AI_OPTIMIZER_SCHEMA,
        fallback_factory=fallback,
    )

    suggestions = response_data.get("suggestions", [])
    current_ir = list(ir)
    accepted_suggestions: List[Dict[str, Any]] = []
    rejected_suggestions: List[Dict[str, Any]] = []

    for sugg in suggestions[:max_suggestions]:
        sugg_id = str(sugg.get("suggestion_id", "opt"))
        desc = str(sugg.get("description", "Proposed optimization"))
        target_indices = sugg.get("target_indices", [])
        raw_replacements = sugg.get("replacement_instructions", [])

        # Validate target_indices
        if not isinstance(target_indices, list):
            rejected_suggestions.append({
                "suggestion_id": sugg_id,
                "description": desc,
                "reason": f"Invalid target_indices type: {type(target_indices)}",
            })
            continue

        if any(not isinstance(i, int) or i < 0 or i >= len(current_ir) for i in target_indices):
            rejected_suggestions.append({
                "suggestion_id": sugg_id,
                "description": desc,
                "reason": f"target_indices out of bounds for IR of length {len(current_ir)}: {target_indices}",
            })
            continue

        # Parse replacement instructions
        try:
            replacement_insts = [dict_to_instruction(d) for d in raw_replacements]
        except Exception as exc:
            rejected_suggestions.append({
                "suggestion_id": sugg_id,
                "description": desc,
                "reason": f"Failed to parse replacement instructions: {exc}",
            })
            continue

        # Construct candidate IR
        candidate_ir = apply_suggestion_patch(current_ir, target_indices, replacement_insts)

        # Run candidate IR through interpreter for equivalence check
        cand_ok, cand_output, cand_err = run_safely(candidate_ir)
        if not cand_ok:
            rejected_suggestions.append({
                "suggestion_id": sugg_id,
                "description": desc,
                "reason": f"Candidate execution raised runtime error: {cand_err}",
            })
            continue

        # Strictly assert identical observable output
        if cand_output == base_output:
            accepted_suggestions.append({
                "suggestion_id": sugg_id,
                "description": desc,
                "reason": "Equivalence verified: interpreter output matched baseline.",
                "target_indices": target_indices,
                "instructions_removed": len(target_indices),
                "instructions_inserted": len(replacement_insts),
                "instruction_delta": len(candidate_ir) - len(current_ir),
            })
            current_ir = candidate_ir
        else:
            rejected_suggestions.append({
                "suggestion_id": sugg_id,
                "description": desc,
                "reason": f"Output mismatch: expected {base_output}, got {cand_output}",
            })

    return {
        "analysis": response_data.get("analysis", ""),
        "initial_ir": ir,
        "optimized_ir": current_ir,
        "accepted_suggestions": accepted_suggestions,
        "rejected_suggestions": rejected_suggestions,
        "initial_instruction_count": len(ir),
        "final_instruction_count": len(current_ir),
        "equivalence_verified": True,
    }


def optimize_program_with_ai(
    source_code: str,
    client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    """
    Convenience end-to-end entry point: compiles source code to IR,
    runs the AI optimizer with equivalence verification, and returns the results.
    """
    lexer = Lexer(source_code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    analyzer = SemanticAnalyzer()
    analyzer.analyze(ast)
    ir = generate_ir(ast)

    return ai_optimize_ir(ir, client=client)
