"""
optimizer.py
------------
Optimization passes on Three-Address Code (TAC) Intermediate Representation.

Passes:
  1. constant_folding: Computes compile-time binary/unary operations on constants.
  2. constant_propagation: Propagates known constant values into subsequent uses.
  3. algebraic_simplification: Applies algebraic identities (e.g., x*1, x+0, x*0).
  4. common_subexpression_elimination: Eliminates duplicate computations within basic blocks.
  5. dead_code_elimination: Eliminates unreachable instructions and unused variable assignments.

Each pass is an independent function reporting how many instructions it removed or simplified.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from core.ir import Const, Instruction, Operand


# ── Pass 1: Constant Folding ──────────────────────────────────────────────────

def constant_folding(instructions: List[Instruction]) -> Tuple[List[Instruction], int]:
    """
    Evaluate binary and unary expressions with known literal constants at compile time.
    Replaces BINOP/UNOP with ASSIGN Const(result).
    Returns (new_instructions, count_simplified).
    """
    new_insts: List[Instruction] = []
    count = 0

    for inst in instructions:
        # Binary Operations
        if (
            inst.op in ("+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||")
            and isinstance(inst.arg1, Const)
            and isinstance(inst.arg2, Const)
            and inst.result is not None
        ):
            c1 = inst.arg1.value
            c2 = inst.arg2.value
            try:
                val: Any = None
                if inst.op == "+":
                    val = c1 + c2
                elif inst.op == "-":
                    val = c1 - c2
                elif inst.op == "*":
                    val = c1 * c2
                elif inst.op == "/":
                    if c2 != 0:
                        val = c1 // c2 if isinstance(c1, int) and isinstance(c2, int) else c1 / c2
                elif inst.op == "%":
                    if c2 != 0:
                        val = c1 % c2
                elif inst.op == "==":
                    val = (c1 == c2)
                elif inst.op == "!=":
                    val = (c1 != c2)
                elif inst.op == "<":
                    val = (c1 < c2)
                elif inst.op == "<=":
                    val = (c1 <= c2)
                elif inst.op == ">":
                    val = (c1 > c2)
                elif inst.op == ">=":
                    val = (c1 >= c2)
                elif inst.op == "&&":
                    val = bool(c1 and c2)
                elif inst.op == "||":
                    val = bool(c1 or c2)

                if val is not None:
                    new_insts.append(Instruction("ASSIGN", result=inst.result, arg1=Const(val)))
                    count += 1
                    continue
            except (ZeroDivisionError, TypeError):
                pass

        # Unary Operations
        if (
            inst.op in ("!", "-u", "+u")
            and isinstance(inst.arg1, Const)
            and inst.result is not None
        ):
            c = inst.arg1.value
            try:
                val = None
                if inst.op == "!":
                    val = not c
                elif inst.op == "-u":
                    val = -c
                elif inst.op == "+u":
                    val = +c

                if val is not None:
                    new_insts.append(Instruction("ASSIGN", result=inst.result, arg1=Const(val)))
                    count += 1
                    continue
            except TypeError:
                pass

        new_insts.append(inst)

    return new_insts, count


# ── Pass 2: Constant Propagation ──────────────────────────────────────────────

def constant_propagation(instructions: List[Instruction]) -> Tuple[List[Instruction], int]:
    """
    Propagate constant values into operand uses within basic blocks.
    Returns (new_instructions, count_propagated).
    """
    new_insts: List[Instruction] = []
    constants: Dict[str, Const] = {}
    count = 0

    for inst in instructions:
        # Control-flow boundaries invalidate local basic-block constants
        if inst.op in ("LABEL", "JUMP", "JUMP_IF", "JUMP_IF_FALSE", "CALL", "RETURN", "FUNC_BEGIN", "FUNC_END"):
            constants.clear()

        # Check arg1 substitution
        arg1 = inst.arg1
        if isinstance(arg1, str) and arg1 in constants:
            arg1 = constants[arg1]
            count += 1

        # Check arg2 substitution
        arg2 = inst.arg2
        if isinstance(arg2, str) and arg2 in constants:
            arg2 = constants[arg2]
            count += 1

        new_inst = Instruction(op=inst.op, result=inst.result, arg1=arg1, arg2=arg2)
        new_insts.append(new_inst)

        # Update known constants
        if new_inst.op == "ASSIGN" and new_inst.result is not None and isinstance(new_inst.arg1, Const):
            constants[new_inst.result] = new_inst.arg1
        elif new_inst.result is not None:
            # Overwritten variable is no longer constant
            constants.pop(new_inst.result, None)

    return new_insts, count


# ── Pass 3: Algebraic Simplification ──────────────────────────────────────────

def algebraic_simplification(instructions: List[Instruction]) -> Tuple[List[Instruction], int]:
    """
    Apply algebraic identities such as:
      x * 1 -> x,  1 * x -> x
      x * 0 -> 0,  0 * x -> 0
      x + 0 -> x,  0 + x -> x
      x - 0 -> x
      x / 1 -> x
      x && true -> x,  true && x -> x
      x && false -> false, false && x -> false
      x || false -> x, false || x -> x
      x || true -> true, true || x -> true
    Returns (new_instructions, count_simplified).
    """
    new_insts: List[Instruction] = []
    count = 0

    def is_const_val(opnd: Optional[Operand], expected: Any) -> bool:
        if isinstance(opnd, Const):
            if type(expected) is bool:
                return type(opnd.value) is bool and opnd.value == expected
            if type(expected) in (int, float):
                return type(opnd.value) in (int, float) and type(opnd.value) is not bool and opnd.value == expected
            return opnd.value == expected
        return False

    for inst in instructions:
        if inst.result is None:
            new_insts.append(inst)
            continue

        op = inst.op
        a1 = inst.arg1
        a2 = inst.arg2

        simplified: Optional[Operand] = None

        # Multiplication
        if op == "*":
            if is_const_val(a1, 1):
                simplified = a2
            elif is_const_val(a2, 1):
                simplified = a1
            elif is_const_val(a1, 0) or is_const_val(a2, 0):
                # Match type of 0
                zero_val = 0.0 if (isinstance(a1, Const) and isinstance(a1.value, float)) or (isinstance(a2, Const) and isinstance(a2.value, float)) else 0
                simplified = Const(zero_val)

        # Addition
        elif op == "+":
            if is_const_val(a1, 0):
                simplified = a2
            elif is_const_val(a2, 0):
                simplified = a1

        # Subtraction
        elif op == "-":
            if is_const_val(a2, 0):
                simplified = a1

        # Division
        elif op == "/":
            if is_const_val(a2, 1):
                simplified = a1

        # Logical AND
        elif op == "&&":
            if is_const_val(a1, True):
                simplified = a2
            elif is_const_val(a2, True):
                simplified = a1
            elif is_const_val(a1, False) or is_const_val(a2, False):
                simplified = Const(False)

        # Logical OR
        elif op == "||":
            if is_const_val(a1, False):
                simplified = a2
            elif is_const_val(a2, False):
                simplified = a1
            elif is_const_val(a1, True) or is_const_val(a2, True):
                simplified = Const(True)

        if simplified is not None:
            new_insts.append(Instruction("ASSIGN", result=inst.result, arg1=simplified))
            count += 1
        else:
            new_insts.append(inst)

    return new_insts, count


# ── Pass 4: Common Subexpression Elimination (CSE) ───────────────────────────

def common_subexpression_elimination(instructions: List[Instruction]) -> Tuple[List[Instruction], int]:
    """
    Eliminate duplicate expressions within basic blocks.
    Replaces redundant computations with copy assignments.
    Returns (new_instructions, count_eliminated).
    """
    new_insts: List[Instruction] = []
    # Map (op, arg1, arg2) -> result_variable
    available: Dict[Tuple[str, Any, Any], str] = {}
    count = 0

    COMMUTATIVE_OPS = {"+", "*", "==", "!=", "&&", "||"}

    for inst in instructions:
        # Control-flow boundaries reset available expressions
        if inst.op in ("LABEL", "JUMP", "JUMP_IF", "JUMP_IF_FALSE", "CALL", "RETURN", "FUNC_BEGIN", "FUNC_END"):
            available.clear()

        if inst.op in ("+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||") and inst.result:
            key = (inst.op, inst.arg1, inst.arg2)
            if key in available:
                prev_var = available[key]
                new_insts.append(Instruction("ASSIGN", result=inst.result, arg1=prev_var))
                count += 1
                continue

            # Before registering new result, invalidate old entries where inst.result was an operand or stored result
            res = inst.result
            to_del = [
                k for k in available
                if k[1] == res or k[2] == res or available[k] == res
            ]
            for k in to_del:
                del available[k]

            # Record expression
            available[key] = inst.result
            if inst.op in COMMUTATIVE_OPS:
                available[(inst.op, inst.arg2, inst.arg1)] = inst.result
        else:
            # If any other instruction assigns to a variable, invalidate expressions using or holding it
            if inst.result is not None:
                res = inst.result
                to_del = [
                    k for k in available
                    if k[1] == res or k[2] == res or available[k] == res
                ]
                for k in to_del:
                    del available[k]

        new_insts.append(inst)

    return new_insts, count


# ── Pass 5: Dead-Code Elimination (DCE) ───────────────────────────────────────

def dead_code_elimination(instructions: List[Instruction]) -> Tuple[List[Instruction], int]:
    """
    Eliminates unreachable instructions after jumps/returns and removes
    unused variable/temporary assignments that have no side effects.
    Returns (new_instructions, count_removed).
    """
    total_removed = 0
    current = list(instructions)

    # 1. Unreachable Code Elimination
    reachable: List[Instruction] = []
    unreachable = False

    for inst in current:
        if inst.op in ("LABEL", "FUNC_BEGIN"):
            unreachable = False

        if not unreachable:
            reachable.append(inst)
        else:
            total_removed += 1

        if inst.op in ("JUMP", "RETURN", "HALT"):
            unreachable = True

    current = reachable

    # 2. Iterative Dead Variable / Temporary Elimination
    while True:
        # Collect all used variable/temporary names
        used_names: Set[str] = set()
        for inst in current:
            if isinstance(inst.arg1, str):
                used_names.add(inst.arg1)
            if isinstance(inst.arg2, str):
                used_names.add(inst.arg2)

        # Filter out unused assignments
        filtered: List[Instruction] = []
        pass_removed = 0

        for inst in current:
            # Side-effecting operations cannot be eliminated
            if inst.op in ("CALL", "PARAM", "PRINT", "RETURN", "JUMP", "JUMP_IF", "JUMP_IF_FALSE", "LABEL", "FUNC_BEGIN", "FUNC_END", "HALT"):
                filtered.append(inst)
            elif inst.result is not None and inst.result not in used_names:
                # Dead assignment!
                pass_removed += 1
            else:
                filtered.append(inst)

        total_removed += pass_removed
        current = filtered
        if pass_removed == 0:
            break

    return current, total_removed


# ── Top-Level Optimization Pipeline ───────────────────────────────────────────

def optimize(
    instructions: List[Instruction],
    max_iterations: int = 10,
) -> Tuple[List[Instruction], Dict[str, int]]:
    """
    Run an iterative fixed-point optimization pipeline over TAC instructions.
    Returns (optimized_instructions, statistics_dict).
    """
    stats: Dict[str, int] = {
        "constant_folding": 0,
        "constant_propagation": 0,
        "algebraic_simplification": 0,
        "common_subexpression_elimination": 0,
        "dead_code_elimination": 0,
        "total_removed": 0,
    }

    initial_count = len(instructions)
    current = list(instructions)

    for _ in range(max_iterations):
        iter_changed = 0

        # Pass 1: Constant Propagation
        current, c_prop = constant_propagation(current)
        stats["constant_propagation"] += c_prop
        iter_changed += c_prop

        # Pass 2: Constant Folding
        current, c_fold = constant_folding(current)
        stats["constant_folding"] += c_fold
        iter_changed += c_fold

        # Pass 3: Algebraic Simplification
        current, c_alg = algebraic_simplification(current)
        stats["algebraic_simplification"] += c_alg
        iter_changed += c_alg

        # Pass 4: Common Subexpression Elimination
        current, c_cse = common_subexpression_elimination(current)
        stats["common_subexpression_elimination"] += c_cse
        iter_changed += c_cse

        # Pass 5: Dead-Code Elimination
        current, c_dce = dead_code_elimination(current)
        stats["dead_code_elimination"] += c_dce
        iter_changed += c_dce

        if iter_changed == 0:
            break

    stats["total_removed"] = max(0, initial_count - len(current))
    return current, stats
