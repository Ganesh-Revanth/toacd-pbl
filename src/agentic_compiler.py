"""
agentic_compiler.py
-------------------
Autonomous ReAct (Reason + Act + Reflect) Compiler Agent for the Green Self-Healing Compiler.
Powered by Google AI Studio (Gemini) via the unified LLMClient.
Integrated with AAI Security Guardrail: Ingress injection defense & egress trojan detection.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional

from agent_tools import _resolve_language, compile_code, inspect_ast, security_audit, try_fast_heal
from aai_guardrail import AAIGuardrail, GuardrailResult
from ai.llm_client import (
    DEFAULT_MODEL,
    GEMINI_API_BASE,
    GEMINI_MODELS,
    GeminiProvider,
    GuardrailSecurityException,
    LLMClient,
    get_stored_api_key,
)

_TOOLCHAIN_NAMES: Dict[str, str] = {
    "cpp": "g++",
    "c": "gcc",
    "python": "python (py_compile)",
    "java": "javac",
}


AI_CONFIG_FILE = "ai_config.json"


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
      4. Powered by Google AI Studio with high token capacity via LLMClient
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_iterations: int = 6,
        client: Optional[LLMClient] = None,
        language: Any = "cpp",
    ):
        self.api_key = api_key or get_stored_api_key()
        self.model = model or DEFAULT_MODEL
        self.max_iterations = max_iterations
        self.language = language
        self.guardrail = AAIGuardrail()
        self.client = client or LLMClient(
            api_key=self.api_key,
            model=self.model,
            guardrail=self.guardrail,
        )

    def _call_gemini(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> str:
        """Call LLM via provider-agnostic LLMClient wrapper."""
        if not self.api_key:
            raise ValueError(
                "Google AI Studio API Key is missing. "
                "Please set the GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable."
            )

        # Synchronize model or key if mutated on CompilerAgent directly
        if isinstance(getattr(self.client, "provider", None), GeminiProvider):
            self.client.provider.api_key = self.api_key
            self.client.provider.model = self.model
        self.client.model = self.model

        response = self.client.generate(messages, temperature=temperature)
        self.model = self.client.active_model
        return response

    def heal(
        self,
        source_code: str,
        file_path: Optional[str] = None,
        on_step: Optional[Callable[[int, str, str, Dict[str, Any]], None]] = None,
        language: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes the Secure Agentic ReAct Healing Loop powered by Google AI Studio.
        """
        lang = _resolve_language(language if language is not None else self.language, file_path)
        lang_id = getattr(lang, "id", "cpp").lower()
        lang_name = getattr(lang, "name", "C++")
        toolchain_name = _TOOLCHAIN_NAMES.get(lang_id, lang_name)

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
        compile_res = compile_code(current_code, file_path, language=lang)
        security_res = security_audit(current_code, file_path, compile_res.get("errors"), language=lang)

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
            fast_patched = try_fast_heal(current_code, first_err, language=lang)
            if fast_patched and fast_patched != current_code:
                test_compile = compile_code(fast_patched, file_path, language=lang)
                test_sec = security_audit(fast_patched, file_path, test_compile.get("errors"), language=lang)
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
            ) or f"None (Clean {toolchain_name} compilation)"

            sec_bullets = "\n".join(
                f"- Line {f.get('line')}: [{f.get('severity')}] {f.get('vulnerability_type')} -> {f.get('description')} [Fix Hint: {f.get('recommendation', 'Fix safely')}]"
                for f in security_res.get("findings", [])
            ) or "None (Clean security profile)"

            system_prompt = (
                f"You are an expert Autonomous {lang_name} Compiler and Security Agent for a Green Self-Healing Compiler using {toolchain_name}.\n"
                f"Your objective is to fix all compilation errors and security vulnerabilities in the provided {lang_name} code.\n"
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
                f"[Provide the COMPLETE fixed {lang_name} code here without markdown fences]\n"
                "</patched_code>"
            )

            user_prompt = (
                f"Iteration: {step} of {self.max_iterations}\n\n"
                f"### CURRENT {lang_name.upper()} CODE:\n{current_code}\n\n"
                f"### COMPILER DIAGNOSTICS ({toolchain_name}):\n{error_bullets}\n\n"
                f"### SECURITY AUDIT FINDINGS:\n{sec_bullets}\n"
            )

            if history:
                prev_reflections = "\n".join(
                    f"Turn {h['step']}: {h['thought']}\nOutcome: {h['outcome']}"
                    for h in history
                )
                user_prompt += f"\n### PREVIOUS ATTEMPTS & FEEDBACK:\n{prev_reflections}\n"

            # Execute reasoning call via unified LLMClient
            try:
                response = self.client.generate(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    original_code=current_code,
                    language=lang,
                    temperature=0.1,
                )
                self.model = self.client.active_model
            except GuardrailSecurityException as g_exc:
                if g_exc.stage == "EGRESS":
                    egress_check = g_exc.guardrail_result
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
                else:
                    ingress_check = g_exc.guardrail_result
                    if on_step:
                        on_step(
                            step,
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
                        "final_code": current_code,
                        "iterations": step,
                        "history": history,
                        "summary": f"Execution halted by AAI Security Layer: {ingress_check.attack_type}.",
                        "tier": "guardrail_ingress",
                    }
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
                fenced = re.search(r"```(?:cpp|c\+\+|c|python|py|java)?\s*(.*?)\s*```", response, re.DOTALL)
                candidate_code = fenced.group(1).strip() if fenced else current_code

            if candidate_code.startswith("```"):
                candidate_code = re.sub(r"^```[a-zA-Z0-9_\-\+\.]*\n?", "", candidate_code)
            if candidate_code.endswith("```"):
                candidate_code = re.sub(r"\n?```$", "", candidate_code)

            # ── Egress Guardrail: Check for Backdoors/Trojans in Patch ───────────
            egress_check = self.guardrail.scan_egress(source_code, candidate_code, language=lang)
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
            compile_res = compile_code(candidate_code, file_path, language=lang)
            security_res = security_audit(candidate_code, file_path, compile_res.get("errors"), language=lang)

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
