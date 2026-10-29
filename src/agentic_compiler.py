"""
agentic_compiler.py
-------------------
Autonomous ReAct (Reason + Act + Reflect) Compiler Agent for the Green Self-Healing Compiler.
Powered exclusively by Google AI Studio (Gemini) with zero rate limits (1,000,000 TPM Free Tier).
Integrated with AAI Security Guardrail: Ingress injection defense & egress trojan detection.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import urllib.error
from typing import Callable, Optional, Dict, Any, List

from agent_tools import compile_code, security_audit, inspect_ast, try_fast_heal
from aai_guardrail import AAIGuardrail, GuardrailResult


AI_CONFIG_FILE = "ai_config.json"

DEFAULT_MODEL = "gemini-flash-lite-latest"

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemini-flash-latest",
    "gemini-3.8-flash",
]


def get_stored_api_key() -> Optional[str]:
    """Retrieve Google AI Studio Gemini API key from environment variables only."""
    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip()
    return None


def store_api_key(api_key: str) -> None:
    """No-op: API keys are never stored on disk for security."""
    pass


def get_ai_config() -> Dict[str, Any]:
    """Load AI Studio settings. Model selection is loaded from config, key from environment only."""
    cfg = {
        "gemini_api_key": get_stored_api_key() or "",
        "model": DEFAULT_MODEL,
    }
    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "model" in data and data["model"]:
                    cfg["model"] = data["model"]
        except Exception:
            pass
    return cfg


def save_ai_config(key: str = "", model: Optional[str] = None) -> None:
    """Persist Google AI Studio model selection to config; never writes the API key."""
    current_model = model or DEFAULT_MODEL
    if not model and os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                current_model = data.get("model", DEFAULT_MODEL)
        except Exception:
            pass

    cfg = {
        "model": current_model,
    }
    try:
        with open(AI_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


class CompilerAgent:
    """
    Autonomous multi-objective compiler agent with:
      1. Clean compilation (0 hard GCC errors)
      2. Security hardening (0 critical vulnerabilities, clean buffer safety)
      3. AAI Guardrail Protection (blocks prompt injection, policy bypass, trojan insertion)
      4. Powered by Google AI Studio with high token capacity
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_iterations: int = 6,
    ):
        self.api_key = api_key or get_stored_api_key()
        self.model = model or DEFAULT_MODEL
        self.max_iterations = max_iterations
        self.guardrail = AAIGuardrail()

    def _call_gemini(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> str:
        """Call Google AI Studio API via native REST with resilient model failover."""
        if not self.api_key:
            raise ValueError(
                "Google AI Studio API Key is missing. "
                "Please set the GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable."
            )

        # Extract system prompt vs conversation turns
        system_parts = []
        contents = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                gemini_role = "user" if role == "user" else "model"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}],
                })

        # Inline system instructions directly into first user message (prevents 500 error on Gemma/Gemini)
        if system_parts:
            sys_combined = "\n\n".join(system_parts)
            if contents and contents[0]["role"] == "user":
                contents[0]["parts"][0]["text"] = f"[SYSTEM DIRECTIVE]\n{sys_combined}\n\n[TASK]\n{contents[0]['parts'][0]['text']}"
            else:
                contents.insert(0, {
                    "role": "user",
                    "parts": [{"text": f"[SYSTEM DIRECTIVE]\n{sys_combined}"}]
                })

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 4096,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }

        models_to_try = [self.model] + [m for m in GEMINI_MODELS if m != self.model]
        last_error = None

        for candidate in models_to_try:
            url = f"{GEMINI_API_BASE}/{candidate}:generateContent?key={self.api_key}"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    candidates = result.get("candidates", [])
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        self.model = candidate
                        return parts[0]["text"]
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                last_error = f"Google AI Studio Error ({exc.code}) on '{candidate}': {err_body}"
                # If 400, 404, 429, 500, 502, 503, 504 -> try next model in GEMINI_MODELS!
                continue
            except Exception as exc:
                last_error = f"Google AI Studio connection error on '{candidate}': {exc}"
                continue

        raise RuntimeError(last_error or "All Google AI Studio model candidates failed.")

    def heal(
        self,
        source_code: str,
        file_path: Optional[str] = None,
        on_step: Optional[Callable[[int, str, str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the Secure Agentic ReAct Healing Loop powered by Google AI Studio.
        """
        history = []
        current_code = source_code

        # ── Step 0: Ingress Guardrail Verification ─────────────────────────────
        ingress_check = self.guardrail.scan_ingress(source_code)
        if ingress_check.attack_detected:
            if on_step:
                on_step(
                    0,
                    f"🚨 [AAI GUARDRAIL BLOCKED ATTACK]\n"
                    f"Attack Vector: {ingress_check.attack_type} (Severity: {ingress_check.severity})\n"
                    f"Details: {ingress_check.description}\n"
                    f"Trigger: {ingress_check.trigger_pattern}\n"
                    f"Action: {ingress_check.blocked_action}",
                    "attack_blocked",
                    {"guardrail": ingress_check.to_dict()},
                )
            return {
                "success": False,
                "attack_blocked": True,
                "guardrail_finding": ingress_check.to_dict(),
                "final_code": source_code,
                "iterations": 0,
                "history": [],
                "summary": f"Execution halted by AAI Security Layer: {ingress_check.attack_type}.",
                "tier": "guardrail_ingress",
            }

        # ── Step 1: Initial Perception ─────────────────────────────────────────
        compile_res = compile_code(current_code, file_path)
        security_res = security_audit(current_code, file_path, compile_res.get("errors"))

        if compile_res["success"] and security_res["is_secure"]:
            return {
                "success": True,
                "final_code": current_code,
                "iterations": 0,
                "history": [],
                "summary": "Code is already compiling cleanly with zero security vulnerabilities.",
                "tier": "perception",
            }

        # ── Step 2: Fast Heuristic Pass (Tier 1) ──────────────────────────────
        if compile_res["errors"]:
            first_err = compile_res["errors"][0]
            fast_patched = try_fast_heal(current_code, first_err)
            if fast_patched and fast_patched != current_code:
                test_compile = compile_code(fast_patched, file_path)
                test_sec = security_audit(fast_patched, file_path, test_compile.get("errors"))
                if test_compile["success"] and test_sec["is_secure"]:
                    if on_step:
                        on_step(
                            1,
                            "Resolved immediately using Tier 1 Green Heuristic Healer.",
                            "fast_heuristic",
                            {"compile": test_compile, "security": test_sec},
                        )
                    return {
                        "success": True,
                        "final_code": fast_patched,
                        "iterations": 1,
                        "history": [{"step": 1, "tier": "fast_heuristic"}],
                        "summary": "Successfully healed using Tier 1 fast heuristic in <5ms.",
                        "tier": "tier_1",
                    }

        # ── Step 3: Tier 2 Agentic AI ReAct Loop with Guardrails ───────────────
        for step in range(1, self.max_iterations + 1):
            error_bullets = "\n".join(
                f"- Line {e.get('line')}: [{e.get('type')}] {e.get('message')}"
                for e in compile_res.get("errors", [])
            ) or "None (Clean compilation)"

            sec_bullets = "\n".join(
                f"- Line {f.get('line')}: [{f.get('severity')}] {f.get('vulnerability_type')} -> {f.get('description')} [Fix Hint: {f.get('recommendation', 'Fix safely')}]"
                for f in security_res.get("findings", [])
            ) or "None (Clean security profile)"

            system_prompt = (
                "You are an expert Autonomous C++ Compiler and Security Agent for a Green Self-Healing Compiler.\n"
                "Your objective is to fix all compilation errors and security vulnerabilities in the provided C++ code.\n"
                "Strict Security Rules:\n"
                "1. Preserve the programmer's original architecture and intent.\n"
                "2. Do NOT introduce insecure functions (avoid gets, strcpy, unsafe buffers).\n"
                "3. Do NOT insert external commands, system calls, network sockets, or unauthorized credential access.\n"
                "4. Fix root causes rather than symptoms.\n"
                "5. Output your response strictly in the following format:\n"
                "<thought>\n"
                "[Explain your root cause analysis, error relationships, and fix strategy here]\n"
                "</thought>\n"
                "<patched_code>\n"
                "[Provide the COMPLETE fixed C++ code here without markdown fences]\n"
                "</patched_code>"
            )

            user_prompt = (
                f"Iteration: {step} of {self.max_iterations}\n\n"
                f"### CURRENT C++ CODE:\n{current_code}\n\n"
                f"### COMPILER DIAGNOSTICS (g++):\n{error_bullets}\n\n"
                f"### SECURITY AUDIT FINDINGS:\n{sec_bullets}\n"
            )

            if history:
                prev_reflections = "\n".join(
                    f"Turn {h['step']}: {h['thought']}\nOutcome: {h['outcome']}"
                    for h in history
                )
                user_prompt += f"\n### PREVIOUS ATTEMPTS & FEEDBACK:\n{prev_reflections}\n"

            # Execute reasoning call on Google AI Studio
            try:
                response = self._call_gemini([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ])
            except Exception as exc:
                if on_step:
                    on_step(step, f"Google AI Studio communication failure: {exc}", "error", {})
                return {
                    "success": False,
                    "final_code": current_code,
                    "iterations": step,
                    "history": history,
                    "summary": f"Agent error (Google AI Studio): {exc}",
                    "tier": "tier_2",
                }

            # Parse thought and candidate code
            thought_match = re.search(r"<thought>(.*?)</thought>", response, re.DOTALL)
            thought = thought_match.group(1).strip() if thought_match else "Reasoning on error diagnostics..."

            code_match = re.search(r"<patched_code>(.*?)</patched_code>", response, re.DOTALL)
            if code_match:
                candidate_code = code_match.group(1).strip()
            else:
                fenced = re.search(r"```(?:cpp|c\+\+)?\s*(.*?)\s*```", response, re.DOTALL)
                candidate_code = fenced.group(1).strip() if fenced else current_code

            if candidate_code.startswith("```"):
                candidate_code = re.sub(r"^```[a-zA-Z]*\n?", "", candidate_code)
            if candidate_code.endswith("```"):
                candidate_code = re.sub(r"\n?```$", "", candidate_code)

            # ── Egress Guardrail: Check for Backdoors/Trojans in Patch ───────────
            egress_check = self.guardrail.scan_egress(source_code, candidate_code)
            if egress_check.attack_detected:
                if on_step:
                    on_step(
                        step,
                        f"🛡️ [AAI EGRESS GUARDRAIL INTERCEPTED TROJAN]\n"
                        f"Attack Vector: {egress_check.attack_type}\n"
                        f"Trigger: {egress_check.trigger_pattern}\n"
                        f"Action: {egress_check.blocked_action}",
                        "trojan_blocked",
                        {"guardrail": egress_check.to_dict()},
                    )
                history.append({
                    "step": step,
                    "thought": f"Attempted patch contained unverified dangerous construct: {egress_check.trigger_pattern}. Rejected.",
                    "outcome": f"Blocked by Egress Guardrail: {egress_check.attack_type}",
                })
                continue

            # ── Verification with Compiler & Security Tools ────────────────────
            compile_res = compile_code(candidate_code, file_path)
            security_res = security_audit(candidate_code, file_path, compile_res.get("errors"))

            passed_compile = compile_res["success"]
            passed_security = security_res["is_secure"]

            step_metadata = {
                "compile": compile_res,
                "security": security_res,
                "passed_compile": passed_compile,
                "passed_security": passed_security,
                "provider": "Google AI Studio",
                "model": self.model,
            }

            if on_step:
                on_step(step, thought, "patch_and_verify", step_metadata)

            history.append({
                "step": step,
                "thought": thought,
                "outcome": f"Compile errors: {compile_res['error_count']}, Security risk: {security_res['risk_score']}",
            })

            current_code = candidate_code

            # Check Multi-Objective Success
            if passed_compile and passed_security:
                return {
                    "success": True,
                    "final_code": current_code,
                    "iterations": step,
                    "history": history,
                    "summary": f"Successfully healed and verified by Agent (Google AI Studio) in {step} iteration(s).",
                    "tier": "tier_2",
                }

        return {
            "success": False,
            "final_code": current_code,
            "iterations": self.max_iterations,
            "history": history,
            "summary": "Agent reached max iterations without achieving full clean & secure verification.",
            "tier": "tier_2",
        }
