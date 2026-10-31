"""
aai_guardrail.py
----------------
Agentic AI (AAI) Security Guardrail & Adversarial Attack Detection Layer.
Implements OWASP LLM & Agentic AI Security standards:
  1. Ingress Guardrail: Detects direct & indirect prompt injection, policy bypass, role confusion.
  2. Egress Guardrail: Detects trojan insertion, covert data exfiltration, unauthorized system/exec calls.
  3. Audit Logger: Records tamper attempts, attack payloads, and security decisions.
  4. Detection Metrics Engine: Computes Precision, Recall, F1, ASR (Attack Success Rate), and FPR.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any


AUDIT_LOG_FILE = "data/aai_security_audit.jsonl"


@dataclass
class GuardrailResult:
    is_safe: bool
    attack_detected: bool
    attack_type: Optional[str] = None
    severity: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    description: str = ""
    trigger_pattern: Optional[str] = None
    blocked_action: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AAIGuardrail:
    """
    Two-Tier Security Guardrail for Agentic AI:
      - Ingress: Scans prompts and C++ code comments/strings for adversarial manipulation.
      - Egress: Scans generated C++ patches for trojans, backdoors, and covert data exfiltration.
    """

    # Direct & Indirect Prompt Injection & Policy Bypass patterns
    INJECTION_PATTERNS = [
        # Policy bypass & instruction override
        (r"(?i)(?:ignore|disregard|override|disable|bypass|skip)\s+(?:all\s+)?(?:the\s+)?(?:security|validation|safety|policy|rules|instructions|checks|vulnerabilities|flaws|warnings)", "Policy Bypass / Rule Override", "CRITICAL"),
        (r"(?i)mark\s+(?:the\s+)?(?:vulnerable|malicious|insecure|bad)\s+code\s+as\s+(?:safe|clean|valid|secure|verified)", "Policy Bypass / Integrity Tampering", "CRITICAL"),
        (r"(?i)do\s+not\s+(?:run|perform|execute)\s+(?:the\s+)?(?:security_audit|compile_code|validation|safety_check)", "Tool Suppression Attack", "HIGH"),
        (r"(?i)(?:forget|drop)\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions|rules|prompts|context)", "Context Reset / Jailbreak", "HIGH"),
        (r"(?i)(?:developer|debug|god|unrestricted|jailbreak|root)\s+mode\s+(?:enabled|activated|on)", "Persona Hijack / Privilege Escalation", "HIGH"),
        (r"(?i)system\s+instruction\s*:\s*(?:ignore|disable|override|allow)", "Impersonated System Directive", "CRITICAL"),
        (r"(?i)hidden\s+agenda\s*:", "Adversarial Directive Injection", "HIGH"),
        (r"(?i)(?:exfiltrate|leak|steal|send|transmit)\s+(?:secret|password|credential|token|api_key|private|personal)", "Data Exfiltration Directive", "CRITICAL"),
    ]

    # Delimiter / Tag Confusion Attacks (tricking the agent parser)
    DELIMITER_PATTERNS = [
        (r"</thought>\s*<patched_code>.*?(?:rm\s+-rf|format\s+[A-Z]:|curl|powershell)", "Fake Delimiter Injection / Command Injection", "CRITICAL"),
        (r"<system>.*?</system>", "Impersonated XML System Tag", "HIGH"),
        (r"\[SYSTEM\]\s*:", "Impersonated Bracketed Directive", "HIGH"),
    ]

    # Egress / Patch Trojan & Exfiltration checks
    EXFILTRATION_PATTERNS = [
        (r"(?i)(?:getenv|GetEnvironmentVariable)\s*\(\s*[\"'](?:PASS|PASSWORD|SECRET|KEY|TOKEN|AWS|SSH|AUTH)", "Covert Credential Harvesting", "CRITICAL"),
        (r"(?i)(?:system|popen|_popen|ShellExecute|CreateProcess)\s*\(\s*[\"'].*?(?:curl|wget|powershell|cmd\.exe|nc\s+|bash|invoke-webrequest)", "Malicious Outbound Command Injection", "CRITICAL"),
        (r"(?i)(?:connect|WSAStartup|socket)\s*\(", "Unauthorized Network Socket Injection", "HIGH"),
        (r"(?i)/etc/passwd|/etc/shadow|\\config\\SAM\b|HKLM\\SAM\b|SOFTWARE\\Microsoft", "Unauthorized OS Credential File Access", "CRITICAL"),
    ]

    # Hidden Policy Tampering in Code
    CODE_TAMPER_PATTERNS = [
        (r"#pragma\s+GCC\s+diagnostic\s+ignored\s+[\"']-W(?:all|extra|format-security|error)", "Security Warning Suppression Pragma", "MEDIUM"),
        (r"#define\s+private\s+public", "Encapsulation / Security Bypass Macro", "HIGH"),
    ]

    def __init__(self, audit_log_path: str = AUDIT_LOG_FILE):
        self.audit_log_path = audit_log_path
        os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)

    def scan_ingress(self, text_or_code: str) -> GuardrailResult:
        """
        Ingress Filter: Inspects prompt text, user queries, and source code comments/strings
        for adversarial instructions, jailbreaks, or policy override attempts.
        """
        start_time = time.perf_counter()

        # 1. Check direct & indirect prompt injection patterns
        for pattern, attack_name, severity in self.INJECTION_PATTERNS:
            match = re.search(pattern, text_or_code)
            if match:
                elapsed = (time.perf_counter() - start_time) * 1000
                res = GuardrailResult(
                    is_safe=False,
                    attack_detected=True,
                    attack_type="Prompt Injection: " + attack_name,
                    severity=severity,
                    description=f"Detected adversarial injection attempting to {attack_name.lower()}.",
                    trigger_pattern=match.group(0),
                    blocked_action="Blocked agent execution before invoking LLM reasoning.",
                    latency_ms=elapsed,
                )
                self.log_attack("INGRESS", res, text_or_code)
                return res

        # 2. Check for delimiter hijacking / tag confusion
        for pattern, attack_name, severity in self.DELIMITER_PATTERNS:
            match = re.search(pattern, text_or_code, re.DOTALL)
            if match:
                elapsed = (time.perf_counter() - start_time) * 1000
                res = GuardrailResult(
                    is_safe=False,
                    attack_detected=True,
                    attack_type="Delimiter Hijacking: " + attack_name,
                    severity=severity,
                    description=f"Detected attempt to spoof structural agent XML/delimiter tags.",
                    trigger_pattern=match.group(0)[:60],
                    blocked_action="Blocked agent prompt parsing.",
                    latency_ms=elapsed,
                )
                self.log_attack("INGRESS", res, text_or_code)
                return res

        elapsed = (time.perf_counter() - start_time) * 1000
        return GuardrailResult(
            is_safe=True,
            attack_detected=False,
            severity="LOW",
            description="Ingress input verified clean of prompt injection and policy bypass vectors.",
            latency_ms=elapsed,
        )

    def scan_egress(self, original_code: str, candidate_patch: str, language: Optional[Any] = None) -> GuardrailResult:
        """
        Egress Filter: Inspects the generated patch to verify the AI did not insert
        covert data exfiltration trojans, unauthorized shell commands, backdoor logic,
        or language-specific safety policy violations.
        """
        start_time = time.perf_counter()

        # Check for covert exfiltration / trojan patterns
        for pattern, attack_name, severity in self.EXFILTRATION_PATTERNS:
            match = re.search(pattern, candidate_patch)
            # Flag if introduced in the patch (i.e., wasn't already in original code or is inherently critical)
            if match:
                matched_snippet = match.group(0)
                if matched_snippet not in original_code or severity == "CRITICAL":
                    elapsed = (time.perf_counter() - start_time) * 1000
                    res = GuardrailResult(
                        is_safe=False,
                        attack_detected=True,
                        attack_type="Trojan/Backdoor: " + attack_name,
                        severity=severity,
                        description=f"Generated code introduced covert security hazard: {attack_name}.",
                        trigger_pattern=matched_snippet,
                        blocked_action="Rejected generated patch and prevented code replacement.",
                        latency_ms=elapsed,
                    )
                    self.log_attack("EGRESS", res, candidate_patch)
                    return res

        # Check for code tampering macros/pragmas
        for pattern, attack_name, severity in self.CODE_TAMPER_PATTERNS:
            match = re.search(pattern, candidate_patch)
            if match and match.group(0) not in original_code:
                elapsed = (time.perf_counter() - start_time) * 1000
                res = GuardrailResult(
                    is_safe=False,
                    attack_detected=True,
                    attack_type="Policy Tampering: " + attack_name,
                    severity=severity,
                    description=f"Generated code contains compiler security suppression directive: {attack_name}.",
                    trigger_pattern=match.group(0),
                    blocked_action="Rejected patch; forced re-synthesis with strict security.",
                    latency_ms=elapsed,
                )
                self.log_attack("EGRESS", res, candidate_patch)
                return res

        # Language-aware safety check using language.is_safe()
        lang_obj = None
        if language is not None:
            if isinstance(language, str):
                from languages import get_language
                lang_obj = get_language(language)
            elif hasattr(language, "is_safe"):
                lang_obj = language

        if lang_obj is not None:
            safe, reason = lang_obj.is_safe(candidate_patch)
            if not safe:
                elapsed = (time.perf_counter() - start_time) * 1000
                res = GuardrailResult(
                    is_safe=False,
                    attack_detected=True,
                    attack_type=f"Language Safety Violation ({lang_obj.name})",
                    severity="CRITICAL",
                    description=f"Generated patch violates {lang_obj.name} security policy: {reason}",
                    trigger_pattern=reason,
                    blocked_action="Rejected generated patch and prevented code replacement.",
                    latency_ms=elapsed,
                )
                self.log_attack("EGRESS", res, candidate_patch)
                return res

        elapsed = (time.perf_counter() - start_time) * 1000
        return GuardrailResult(
            is_safe=True,
            attack_detected=False,
            severity="LOW",
            description="Egress patch verified clean of backdoors, trojans, and exfiltration vectors.",
            latency_ms=elapsed,
        )

    def log_attack(self, stage: str, result: GuardrailResult, payload: str) -> None:
        """Write structured audit event for academic / security verification."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "attack_detected": result.attack_detected,
            "attack_type": result.attack_type,
            "severity": result.severity,
            "description": result.description,
            "trigger_snippet": result.trigger_pattern,
            "blocked_action": result.blocked_action,
            "latency_ms": round(result.latency_ms, 3),
            "payload_preview": payload[:250].replace("\n", " ").strip(),
        }
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def get_audit_summary(self) -> Dict[str, Any]:
        """Aggregate audit statistics for display and reporting."""
        if not os.path.exists(self.audit_log_path):
            return {"total_events": 0, "attacks_blocked": 0, "breakdown": {}}

        total = 0
        blocked = 0
        breakdown = {}
        try:
            with open(self.audit_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    total += 1
                    if event.get("attack_detected"):
                        blocked += 1
                        atype = event.get("attack_type", "Unknown")
                        breakdown[atype] = breakdown.get(atype, 0) + 1
        except Exception:
            pass

        return {
            "total_events": total,
            "attacks_blocked": blocked,
            "breakdown": breakdown,
        }
