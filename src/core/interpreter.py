"""
interpreter.py
--------------
Virtual Machine and interpreter for MiniC Three-Address Code (TAC).

Executes TAC instructions, supporting:
  - Arithmetic, relational, and logical operations
  - Function calls, parameter passing, and recursion
  - Conditional branching and loops
  - Output capturing for deterministic verification
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from core.ir import Const, Instruction, Operand, generate_ir


@dataclass
class CallFrame:
    """Activation record for a function call."""
    func_name: str
    locals: Dict[str, Any] = field(default_factory=dict)
    return_pc: int = 0
    return_target: Optional[str] = None


class Interpreter:
    """
    Three-Address Code (TAC) Interpreter.
    """

    def __init__(self, instructions: List[Instruction]) -> None:
        self.instructions = instructions
        self.pc: int = 0
        self.globals: Dict[str, Any] = {}
        self.call_stack: List[CallFrame] = []
        self.param_queue: List[Any] = []
        self.output: List[str] = []

        # Precompute label indices and function entry points
        self.labels: Dict[str, int] = {}
        self.func_starts: Dict[str, int] = {}
        self.func_params: Dict[str, List[str]] = {}

        self._preprocess()

    def _preprocess(self) -> None:
        """Scan instructions to map labels and function entry points."""
        for idx, inst in enumerate(self.instructions):
            if inst.op == "LABEL" and isinstance(inst.arg1, str):
                self.labels[inst.arg1] = idx
            elif inst.op == "FUNC_BEGIN" and isinstance(inst.arg1, str):
                self.func_starts[inst.arg1] = idx + 1
                params = inst.arg2 if isinstance(inst.arg2, list) else []
                self.func_params[inst.arg1] = params

    def get_val(self, operand: Optional[Operand]) -> Any:
        """Resolve an operand to its runtime value."""
        if operand is None:
            return None
        if isinstance(operand, Const):
            return operand.value
        if isinstance(operand, str):
            # Check local frame first
            if self.call_stack and operand in self.call_stack[-1].locals:
                return self.call_stack[-1].locals[operand]
            # Check globals
            if operand in self.globals:
                return self.globals[operand]
            # Undefined variable default to 0 / False / None
            return 0
        return operand

    def set_val(self, target: str, value: Any) -> None:
        """Store a value into the current frame (or globals if at top level)."""
        if self.call_stack:
            self.call_stack[-1].locals[target] = value
        else:
            self.globals[target] = value

    def run(self, max_steps: int = 500000) -> List[str]:
        """
        Execute TAC instructions up to max_steps and return collected output lines.
        """
        step = 0
        total_insts = len(self.instructions)

        while self.pc < total_insts and step < max_steps:
            inst = self.instructions[self.pc]
            step += 1
            op = inst.op

            # ── Control Flow Markers ──────────────────────────────────────────
            if op == "HALT":
                break

            if op in ("LABEL", "FUNC_BEGIN", "FUNC_END"):
                self.pc += 1
                continue

            # ── Variable Assignment ───────────────────────────────────────────
            if op in ("ASSIGN", "="):
                if inst.result is not None:
                    self.set_val(inst.result, self.get_val(inst.arg1))
                self.pc += 1
                continue

            # ── Binary Operations ─────────────────────────────────────────────
            if op in ("+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                v1 = self.get_val(inst.arg1)
                v2 = self.get_val(inst.arg2)
                res: Any = None

                if op == "+":
                    res = v1 + v2
                elif op == "-":
                    res = v1 - v2
                elif op == "*":
                    res = v1 * v2
                elif op == "/":
                    if v2 == 0:
                        raise ZeroDivisionError("Division by zero in TAC interpreter")
                    res = v1 // v2 if isinstance(v1, int) and isinstance(v2, int) else v1 / v2
                elif op == "%":
                    if v2 == 0:
                        raise ZeroDivisionError("Modulo by zero in TAC interpreter")
                    res = v1 % v2
                elif op == "==":
                    res = (v1 == v2)
                elif op == "!=":
                    res = (v1 != v2)
                elif op == "<":
                    res = (v1 < v2)
                elif op == "<=":
                    res = (v1 <= v2)
                elif op == ">":
                    res = (v1 > v2)
                elif op == ">=":
                    res = (v1 >= v2)
                elif op == "&&":
                    res = bool(v1 and v2)
                elif op == "||":
                    res = bool(v1 or v2)

                if inst.result is not None:
                    self.set_val(inst.result, res)
                self.pc += 1
                continue

            # ── Unary Operations ──────────────────────────────────────────────
            if op in ("!", "-u", "+u"):
                v = self.get_val(inst.arg1)
                res = None
                if op == "!":
                    res = not v
                elif op == "-u":
                    res = -v
                elif op == "+u":
                    res = +v

                if inst.result is not None:
                    self.set_val(inst.result, res)
                self.pc += 1
                continue

            # ── Jumps & Branching ─────────────────────────────────────────────
            if op == "JUMP":
                target = str(inst.arg1)
                if target in self.labels:
                    self.pc = self.labels[target]
                    continue
                raise RuntimeError(f"Jump to unknown label '{target}'")

            if op == "JUMP_IF_FALSE":
                cond = bool(self.get_val(inst.arg1))
                if not cond:
                    target = str(inst.arg2)
                    if target in self.labels:
                        self.pc = self.labels[target]
                        continue
                    raise RuntimeError(f"Jump to unknown label '{target}'")
                self.pc += 1
                continue

            if op == "JUMP_IF":
                cond = bool(self.get_val(inst.arg1))
                if cond:
                    target = str(inst.arg2)
                    if target in self.labels:
                        self.pc = self.labels[target]
                        continue
                    raise RuntimeError(f"Jump to unknown label '{target}'")
                self.pc += 1
                continue

            # ── Function Calls & Returns ──────────────────────────────────────
            if op == "PARAM":
                self.param_queue.append(self.get_val(inst.arg1))
                self.pc += 1
                continue

            if op == "CALL":
                func_name = str(inst.arg1)
                num_args = int(inst.arg2) if inst.arg2 is not None else 0

                args = [self.param_queue.pop(0) for _ in range(num_args)]

                if func_name not in self.func_starts:
                    raise RuntimeError(f"Call to unknown function '{func_name}'")

                param_names = self.func_params.get(func_name, [])
                frame_locals = {p: a for p, a in zip(param_names, args)}

                frame = CallFrame(
                    func_name=func_name,
                    locals=frame_locals,
                    return_pc=self.pc + 1,
                    return_target=inst.result,
                )
                self.call_stack.append(frame)
                self.pc = self.func_starts[func_name]
                continue

            if op == "RETURN":
                ret_val = self.get_val(inst.arg1) if inst.arg1 is not None else None
                if not self.call_stack:
                    # Returning from top level terminates program
                    break

                frame = self.call_stack.pop()
                if frame.return_target is not None:
                    self.set_val(frame.return_target, ret_val)

                self.pc = frame.return_pc
                continue

            # ── Print Output ──────────────────────────────────────────────────
            if op == "PRINT":
                val = self.get_val(inst.arg1)
                if isinstance(val, bool):
                    text = "true" if val else "false"
                else:
                    text = str(val)
                self.output.append(text)
                self.pc += 1
                continue

            # Unknown instruction: fail loudly. Silently skipping it would let an
            # AI-proposed patch containing a bogus opcode pass the equivalence check.
            raise RuntimeError(f"Unknown TAC instruction op '{op}' at pc={self.pc}")

        if step >= max_steps:
            raise TimeoutError(f"Interpreter exceeded maximum steps limit ({max_steps})")

        return self.output


# ── Top-Level Execution API ───────────────────────────────────────────────────

def run_ir(instructions_or_source: Union[List[Instruction], str]) -> List[str]:
    """
    Execute Three-Address Code or MiniC source code and return captured outputs.
    """
    if isinstance(instructions_or_source, str):
        instructions = generate_ir(instructions_or_source)
    else:
        instructions = instructions_or_source

    vm = Interpreter(instructions)
    return vm.run()
