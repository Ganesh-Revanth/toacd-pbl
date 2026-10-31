"""
llm_client.py
-------------
Provider-agnostic LLM Client for the Green Self-Healing Compiler.

Features:
  - Provider abstraction (Gemini by default, easily swappable)
  - Environment-variable key loading (GEMINI_API_KEY, GOOGLE_API_KEY)
  - Configurable request timeout
  - Exponential backoff retry on transient errors
  - On-disk response caching keyed by SHA256 prompt hash
  - Mock mode (LLM_MOCK=1) for offline testing and demos
  - Mandatory AAI Guardrail routing (ingress & egress checks on every call)
"""

from __future__ import annotations

import abc
import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:
    from aai_guardrail import AAIGuardrail, GuardrailResult
except ImportError:
    from src.aai_guardrail import AAIGuardrail, GuardrailResult


# ── Constants & Configuration ─────────────────────────────────────────────────

DEFAULT_MODEL = "gemini-flash-lite-latest"
DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".cache", "llm_cache")

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


def load_env_file(path: Optional[str] = None) -> bool:
    """
    Convenience utility to load GEMINI_API_KEY / GOOGLE_API_KEY from a local .env file
    into os.environ if not already present.
    """
    env_paths = [path] if path else [
        os.path.join(os.getcwd(), ".env"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
    ]
    for p in env_paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k in ("GEMINI_API_KEY", "GOOGLE_API_KEY") and v:
                                if k not in os.environ:
                                    os.environ[k] = v
                                return True
            except Exception:
                pass
    return False


def get_stored_api_key() -> Optional[str]:
    """Retrieve Gemini API key strictly from environment variables."""
    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip()
    return None


# ── Exceptions ────────────────────────────────────────────────────────────────

class GuardrailSecurityException(RuntimeError):
    """Raised when an AAI Guardrail detects an adversarial attack (ingress or egress)."""

    def __init__(self, guardrail_result: GuardrailResult, stage: str = "INGRESS") -> None:
        self.guardrail_result = guardrail_result
        self.stage = stage
        super().__init__(
            f"AAI Guardrail intercepted {stage} hazard: {guardrail_result.attack_type} "
            f"[{guardrail_result.severity}] - {guardrail_result.description}"
        )


class LLMCommunicationError(RuntimeError):
    """Raised when all retry attempts to the LLM provider fail."""
    pass


# ── Provider Interface & Implementations ──────────────────────────────────────

class LLMProvider(abc.ABC):
    """Abstract interface for LLM model providers."""

    @abc.abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        timeout: float,
    ) -> str:
        """Submit a prompt and return the model's text response."""
        raise NotImplementedError


class GeminiProvider(LLMProvider):
    """Google AI Studio (Gemini) REST API provider with resilient model failover."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
    ) -> None:
        self.api_key = api_key or get_stored_api_key()
        self.model = model or DEFAULT_MODEL
        self.fallback_models = fallback_models or GEMINI_MODELS

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        timeout: float,
    ) -> str:
        if not self.api_key:
            raise ValueError(
                "Google AI Studio API Key is missing. "
                "Please set the GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable."
            )

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

        # Inline system prompt into the first user turn to prevent 500 errors on Gemma/Gemini
        if system_parts:
            sys_combined = "\n\n".join(system_parts)
            if contents and contents[0]["role"] == "user":
                contents[0]["parts"][0]["text"] = (
                    f"[SYSTEM DIRECTIVE]\n{sys_combined}\n\n[TASK]\n{contents[0]['parts'][0]['text']}"
                )
            else:
                contents.insert(0, {
                    "role": "user",
                    "parts": [{"text": f"[SYSTEM DIRECTIVE]\n{sys_combined}"}],
                })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 4096,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SelfHealingCompiler/2.0",
        }

        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_error = None

        for candidate in models_to_try:
            url = f"{GEMINI_API_BASE}/{candidate}:generateContent?key={self.api_key}"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
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
                last_error = f"Gemini API Error ({exc.code}) on '{candidate}': {err_body}"
                if exc.code in (400, 404, 429, 500, 502, 503, 504):
                    continue
                raise
            except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
                last_error = f"Connection error on '{candidate}': {exc}"
                continue

        raise LLMCommunicationError(last_error or "All candidate Gemini models failed.")


class MockProvider(LLMProvider):
    """
    Offline Mock Provider returning deterministic canned responses.
    Activated when LLM_MOCK=1 or mock=True.
    """

    DEFAULT_CANNED_RESPONSE = (
        "<thought>\n"
        "Identified syntax and type errors in the C++ code. Applying clean fix.\n"
        "</thought>\n"
        "<patched_code>\n"
        "#include <iostream>\n"
        "using namespace std;\n"
        "int main() {\n"
        "    cout << \"Hello from Mock Healer\" << endl;\n"
        "    return 0;\n"
        "}\n"
        "</patched_code>"
    )

    def __init__(self, canned_responses: Optional[Dict[str, str]] = None) -> None:
        self.canned_responses: Dict[str, str] = canned_responses or {}

    def register_response(self, trigger_substring: str, response: str) -> None:
        """Register a canned response triggered by a substring in the prompt."""
        self.canned_responses[trigger_substring] = response

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        timeout: float,
    ) -> str:
        prompt_text = " ".join(m.get("content", "") for m in messages)

        for trigger, response in self.canned_responses.items():
            if trigger in prompt_text:
                return response

        # Default fallback response
        return self.DEFAULT_CANNED_RESPONSE


# ── Response Cache ────────────────────────────────────────────────────────────

class DiskResponseCache:
    """Persistent on-disk response cache keyed by SHA256 prompt hash."""

    def __init__(self, cache_dir: str = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = os.path.abspath(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

    def _compute_key(
        self,
        provider_name: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
    ) -> str:
        canonical = json.dumps(
            {
                "provider": provider_name,
                "model": model,
                "messages": messages,
                "temperature": round(temperature, 4),
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get(
        self,
        provider_name: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
    ) -> Optional[str]:
        key = self._compute_key(provider_name, model, messages, temperature)
        file_path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("response")
            except Exception:
                return None
        return None

    def set(
        self,
        provider_name: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        response: str,
    ) -> None:
        key = self._compute_key(provider_name, model, messages, temperature)
        file_path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "key": key,
                        "provider": provider_name,
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "response": response,
                        "timestamp": time.time(),
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

    def clear(self) -> int:
        """Remove all cached responses from disk."""
        cleared = 0
        if os.path.exists(self.cache_dir):
            for fname in os.listdir(self.cache_dir):
                if fname.endswith(".json"):
                    try:
                        os.remove(os.path.join(self.cache_dir, fname))
                        cleared += 1
                    except OSError:
                        pass
        return cleared


# ── Unified LLM Client ────────────────────────────────────────────────────────

class LLMClient:
    """
    Provider-agnostic LLM Client featuring:
      - Key loading from environment variables only
      - Automatic timeout and exponential backoff retry
      - On-disk SHA256 response caching
      - Offline Mock Mode (LLM_MOCK=1)
      - Mandatory AAI Guardrail ingress and egress inspection
    """

    def __init__(
        self,
        provider: str = "gemini",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        base_delay: float = 0.5,
        backoff_factor: float = 2.0,
        cache_dir: Optional[str] = None,
        use_cache: bool = True,
        mock: Optional[bool] = None,
        mock_mode: Optional[bool] = None,
        guardrail: Optional[AAIGuardrail] = None,
    ) -> None:
        self.provider_name = provider.lower()
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.use_cache = use_cache

        # Determine mock mode: explicit flag (mock or mock_mode), or LLM_MOCK=1 env var
        resolved_mock = mock if mock is not None else mock_mode
        if resolved_mock is not None:
            self.mock_mode = resolved_mock
        else:
            self.mock_mode = os.environ.get("LLM_MOCK", "").lower() in ("1", "true", "yes", "on")

        # Guardrail (mandatory)
        self.guardrail = guardrail if guardrail is not None else AAIGuardrail()

        # Response cache
        self.cache = DiskResponseCache(cache_dir=cache_dir or DEFAULT_CACHE_DIR)

        # Provider initialization
        self.model = model or DEFAULT_MODEL
        if self.mock_mode:
            self.provider = MockProvider()
        elif self.provider_name == "gemini":
            self.provider = GeminiProvider(api_key=api_key, model=self.model)
        else:
            raise ValueError(f"Unsupported LLM provider: '{provider}'. Supported: ['gemini']")

    @property
    def active_model(self) -> str:
        if isinstance(self.provider, GeminiProvider):
            return self.provider.model
        return self.model

    def _extract_candidate_code(self, response: str) -> str:
        """Extract code blocks from standard agent XML tags or markdown fences."""
        code_match = re.search(r"<patched_code>(.*?)</patched_code>", response, re.DOTALL)
        if code_match:
            candidate = code_match.group(1).strip()
        else:
            fenced = re.search(r"```(?:cpp|c\+\+|c|python|py|java)?\s*(.*?)\s*```", response, re.DOTALL)
            candidate = fenced.group(1).strip() if fenced else response.strip()

        if candidate.startswith("```"):
            candidate = re.sub(r"^```[a-zA-Z0-9_\-\+\.]*\n?", "", candidate)
        if candidate.endswith("```"):
            candidate = re.sub(r"\n?```$", "", candidate)
        return candidate

    def generate(
        self,
        messages: List[Dict[str, str]],
        original_code: str = "",
        temperature: float = 0.1,
        language: Optional[Any] = None,
    ) -> str:
        """
        Execute an LLM generation call strictly routed through:
          1. Ingress Guardrail scan on the full prompt
          2. Cache check / Provider call with exponential backoff
          3. Egress Guardrail scan on the generated patch
        """
        # ── 1. Ingress Guardrail Verification ─────────────────────────────────
        prompt_text = "\n".join(m.get("content", "") for m in messages)
        ingress_result = self.guardrail.scan_ingress(prompt_text)
        if ingress_result.attack_detected:
            raise GuardrailSecurityException(ingress_result, stage="INGRESS")

        # ── 2. Credential Validation ──────────────────────────────────────────
        if not self.mock_mode and isinstance(self.provider, GeminiProvider) and not self.provider.api_key:
            raise ValueError("Gemini API Key is missing. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")

        # ── 3. On-Disk Response Cache ─────────────────────────────────────────
        if self.use_cache and not self.mock_mode:
            cached_resp = self.cache.get(self.provider_name, self.active_model, messages, temperature)
            if cached_resp is not None:
                # Still verify cached response through Egress Guardrail for defense-in-depth
                candidate_code = self._extract_candidate_code(cached_resp)
                egress_result = self.guardrail.scan_egress(original_code, candidate_code, language=language)
                if egress_result.attack_detected:
                    raise GuardrailSecurityException(egress_result, stage="EGRESS")
                return cached_resp

        # ── 3. Provider Call with Exponential Backoff ─────────────────────────
        response_text = ""
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                response_text = self.provider.generate(
                    messages=messages,
                    temperature=temperature,
                    timeout=self.timeout,
                )
                break
            except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, TimeoutError, LLMCommunicationError) as exc:
                last_exception = exc
                if attempt == self.max_retries - 1:
                    raise LLMCommunicationError(f"LLM call failed after {self.max_retries} attempts: {exc}") from exc
                delay = self.base_delay * (self.backoff_factor ** attempt)
                time.sleep(delay)
            except Exception as exc:
                # Do not retry on non-transient configuration/argument errors
                raise

        # ── 4. Egress Guardrail Verification ──────────────────────────────────
        candidate_code = self._extract_candidate_code(response_text)
        egress_result = self.guardrail.scan_egress(original_code, candidate_code, language=language)
        if egress_result.attack_detected:
            raise GuardrailSecurityException(egress_result, stage="EGRESS")

        # ── 5. Cache Write ────────────────────────────────────────────────────
        if self.use_cache and not self.mock_mode and response_text:
            self.cache.set(self.provider_name, self.active_model, messages, temperature, response_text)

        return response_text
