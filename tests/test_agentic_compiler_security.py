import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Ensure src/ is on sys.path
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import agentic_compiler
from agentic_compiler import (
    CompilerAgent,
    get_stored_api_key,
    store_api_key,
    get_ai_config,
    save_ai_config,
    DEFAULT_MODEL,
)


class TestAgenticCompilerSecurity(unittest.TestCase):
    """
    Unit tests ensuring API keys are loaded exclusively from environment variables
    and never read from or persisted to ai_config.json.
    """

    def setUp(self):
        # Save original environment
        self._orig_gemini_key = os.environ.get("GEMINI_API_KEY")
        self._orig_google_key = os.environ.get("GOOGLE_API_KEY")
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)

    def tearDown(self):
        # Restore original environment
        if self._orig_gemini_key is not None:
            os.environ["GEMINI_API_KEY"] = self._orig_gemini_key
        else:
            os.environ.pop("GEMINI_API_KEY", None)

        if self._orig_google_key is not None:
            os.environ["GOOGLE_API_KEY"] = self._orig_google_key
        else:
            os.environ.pop("GOOGLE_API_KEY", None)

    def test_key_loaded_from_gemini_api_key_env(self):
        os.environ["GEMINI_API_KEY"] = "gemini-test-secret-key-123"
        self.assertEqual(get_stored_api_key(), "gemini-test-secret-key-123")

    def test_key_loaded_from_google_api_key_env(self):
        os.environ["GOOGLE_API_KEY"] = "google-test-secret-key-456"
        self.assertEqual(get_stored_api_key(), "google-test-secret-key-456")

    def test_key_not_read_from_ai_config_file(self):
        """Even if ai_config.json has a key, get_stored_api_key must ignore it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_config = os.path.join(tmpdir, "ai_config.json")
            with open(fake_config, "w", encoding="utf-8") as f:
                json.dump({"gemini_api_key": "stale-hardcoded-key", "model": "gemini-flash"}, f)

            with patch.object(agentic_compiler, "AI_CONFIG_FILE", fake_config):
                self.assertIsNone(get_stored_api_key())

    def test_store_api_key_never_writes_key_to_disk(self):
        """store_api_key should be a no-op and never write secrets to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_config = os.path.join(tmpdir, "ai_config.json")
            with patch.object(agentic_compiler, "AI_CONFIG_FILE", fake_config):
                store_api_key("attempted-secret-key")
                self.assertFalse(os.path.exists(fake_config))

    def test_save_ai_config_only_saves_model(self):
        """save_ai_config writes model configuration only and never writes the key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_config = os.path.join(tmpdir, "ai_config.json")
            with patch.object(agentic_compiler, "AI_CONFIG_FILE", fake_config):
                save_ai_config(key="secret-to-suppress", model="gemini-3.8-flash")
                self.assertTrue(os.path.exists(fake_config))
                with open(fake_config, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                self.assertEqual(saved_data.get("model"), "gemini-3.8-flash")
                self.assertNotIn("gemini_api_key", saved_data)
                self.assertNotIn("api_key", saved_data)

    def test_get_ai_config_reads_model_and_env_key(self):
        """get_ai_config loads model from file and API key strictly from environment."""
        os.environ["GEMINI_API_KEY"] = "env-secret-xyz"
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_config = os.path.join(tmpdir, "ai_config.json")
            with open(fake_config, "w", encoding="utf-8") as f:
                json.dump({"model": "gemini-3.5-flash"}, f)

            with patch.object(agentic_compiler, "AI_CONFIG_FILE", fake_config):
                cfg = get_ai_config()
                self.assertEqual(cfg["model"], "gemini-3.5-flash")
                self.assertEqual(cfg["gemini_api_key"], "env-secret-xyz")

    def test_compiler_agent_requires_api_key_in_call(self):
        """CompilerAgent raises ValueError if no key is supplied or found in environment."""
        agent = CompilerAgent(api_key=None)
        with self.assertRaises(ValueError) as ctx:
            agent._call_gemini([{"role": "user", "content": "hello"}])
        self.assertIn("API Key is missing", str(ctx.exception))

