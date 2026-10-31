"""
test_web_api.py
---------------
Tests for the local web UI backend (src/web/server.py).

Starts the real HTTP server on an ephemeral port and calls it with urllib, so routing,
JSON handling, static-file safety and the compiler-backed endpoints are all exercised.
Compiler-backed tests are skipped when g++ is not installed.
"""

import json
import os
import shutil
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from web import server  # noqa: E402

HAS_GXX = shutil.which("g++") is not None

MISSING_SEMICOLON = (
    "#include <iostream>\n"
    "int main() {\n"
    "    int x = 5\n"
    "    std::cout << x;\n"
    "    return 0;\n"
    "}\n"
)


class WebApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Make AI behaviour deterministic: no key, no mock.
        cls._saved = {k: os.environ.pop(k, None) for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "LLM_MOCK")}
        cls._orig_key = server._api_key
        server._api_key = lambda: None
        cls.srv = server.make_server("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        server._api_key = cls._orig_key
        for k, v in cls._saved.items():
            if v is not None:
                os.environ[k] = v

    # -- helpers -------------------------------------------------------------
    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def post(self, path, payload=None, raw=None):
        data = raw if raw is not None else json.dumps(payload).encode()
        req = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    # -- static + status -----------------------------------------------------
    def test_index_is_served(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Green Compiler Studio", body)

    def test_path_traversal_is_blocked(self):
        for p in ("/../server.py", "/%2e%2e/server.py", "/..%2f..%2fREADME.md"):
            status, _ = self.get(p)
            self.assertEqual(status, 404, p)

    def test_status_reports_no_ai_without_key(self):
        status, body = self.get("/api/status")
        d = json.loads(body)
        self.assertEqual(status, 200)
        self.assertFalse(d["ai_ready"])
        self.assertFalse(d["llm_mock"])

    def test_samples_include_cpp_language(self):
        d = json.loads(self.get("/api/samples")[1])
        langs = {s["language"] for s in d["samples"]}
        self.assertEqual(langs, {"cpp"})

    def test_benchmark_rates_are_recomputed_from_csv(self):
        status, body = self.get("/api/benchmark")
        if status == 404:
            self.skipTest("results/final.csv not present")
        h = json.loads(body)["healing"]
        self.assertEqual(h["broken"] + h["already_clean"], h["total_fixtures"])
        self.assertAlmostEqual(h["rule_rate"], round(100.0 * h["rule_fixed"] / h["broken"], 1))

    # -- error handling ------------------------------------------------------
    def test_bad_requests_get_json_errors(self):
        self.assertEqual(self.post("/api/cpp/analyze", {})[0], 400)
        self.assertEqual(self.post("/api/cpp/analyze", raw=b"not json")[0], 400)
        self.assertEqual(self.post("/api/nope", {})[0], 404)
        self.assertEqual(self.post("/api/cpp/heal", {"code": "int main(){}", "mode": "weird"})[0], 400)

    def test_ai_endpoints_explain_missing_key(self):
        status, d = self.post("/api/cpp/heal", {"mode": "ai", "code": "int main() { return 0 }"})
        self.assertEqual(status, 412)

    # -- C++ endpoints (need g++) -------------------------------------------
    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_cpp_analyze_finds_missing_semicolon(self):
        status, d = self.post("/api/cpp/analyze", {"code": MISSING_SEMICOLON})
        self.assertEqual(status, 200)
        self.assertFalse(d["ok"])
        self.assertGreaterEqual(d["error_count"], 1)
        self.assertTrue(d["diagnostics"][0]["explanation"])

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_cpp_analyze_clean_code(self):
        d = self.post("/api/cpp/analyze", {"code": "int main() { return 0; }"})[1]
        self.assertTrue(d["ok"])

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_heal_proposes_a_diff_and_does_not_apply_it(self):
        status, d = self.post("/api/cpp/heal", {"mode": "rules", "code": MISSING_SEMICOLON})
        self.assertEqual(status, 200)
        self.assertTrue(d["changed"])
        self.assertTrue(d["compiles"])
        self.assertEqual(d["original"], MISSING_SEMICOLON)
        self.assertIn("int x = 5;", d["patched"])
        kinds = {(l["kind"], l["text"].strip()) for l in d["diff"] if l["kind"] != " "}
        self.assertEqual(kinds, {("-", "int x = 5"), ("+", "int x = 5;")})

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_heal_clean_code_proposes_nothing(self):
        d = self.post("/api/cpp/heal", {"mode": "rules", "code": "int main() { return 0; }"})[1]
        self.assertFalse(d["changed"])
        self.assertTrue(d["compiles"])

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_dangerous_code_is_blocked_before_compiling(self):
        d = self.post("/api/cpp/analyze", {"code": 'int main() { system("ls"); return 0; }'})[1]
        self.assertFalse(d["ok"])
        self.assertIn("Security Error", d["diagnostics"][0]["message"])


    # -- compile / run ---------------------------------------------------------
    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_executes_program_with_stdin(self):
        code = ('#include <iostream>\nint main(){ int a,b; std::cin>>a>>b; '
                'std::cout<<a+b<<"\\n"; std::cerr<<"warn"; return 3; }')
        d = self.post("/api/cpp/run", {"code": code, "stdin": "20 22"})[1]
        self.assertTrue(d["ran"])
        self.assertEqual(d["stdout"].strip(), "42")
        self.assertEqual(d["stderr"], "warn")
        self.assertEqual(d["exit_code"], 3)

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_does_not_run_when_compile_fails(self):
        d = self.post("/api/cpp/run", {"code": MISSING_SEMICOLON})[1]
        self.assertFalse(d["ok"])
        self.assertFalse(d["ran"])
        self.assertGreaterEqual(d["error_count"], 1)

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_stops_infinite_loops(self):
        orig = server.RUN_TIMEOUT_S
        server.RUN_TIMEOUT_S = 1
        try:
            d = self.post("/api/cpp/run", {"code": "int main(){ while(true){} }"})[1]
        finally:
            server.RUN_TIMEOUT_S = orig
        self.assertTrue(d["timed_out"])

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_caps_output(self):
        code = '#include <cstdio>\nint main(){ for(;;) putchar(65); }'
        d = self.post("/api/cpp/run", {"code": code})[1]
        self.assertTrue(d["truncated"] or d["timed_out"])
        self.assertLessEqual(len(d["stdout"]), server.RUN_OUTPUT_CAP)

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_blocks_dangerous_code_and_can_be_disabled(self):
        d = self.post("/api/cpp/run", {"code": 'int main(){ system("ls"); }'})[1]
        self.assertFalse(d["ran"])
        server.RUN_ENABLED = False
        try:
            status, e = self.post("/api/cpp/run", {"code": "int main(){}"})
        finally:
            server.RUN_ENABLED = True
        self.assertEqual(status, 403)

    def test_run_rejects_oversized_stdin(self):
        status, _ = self.post("/api/cpp/run", {"code": "int main(){}", "stdin": "x" * 70000})
        self.assertEqual(status, 400)

    def test_non_loopback_host_disables_run(self):
        srv = server.make_server("0.0.0.0", 0)
        try:
            self.assertFalse(server.RUN_ENABLED)
        finally:
            srv.server_close()
            server.RUN_ENABLED = True


class ScrubPathsTests(unittest.TestCase):
    def test_windows_style_temp_paths_are_removed_without_breaking_json(self):
        wd = "C:\\Users\\me\\AppData\\Local\\Temp\\webui_ab12"
        tree = {"detail": "<" + wd + "\\main.cpp:6:1> x", "children": [{"detail": wd + "/main.cpp"}]}
        out = server._scrub_paths(tree, [wd + "\\", wd.replace("\\", "/") + "/", wd])
        json.dumps(out)  # must stay serialisable
        self.assertNotIn("webui_", json.dumps(out))
        self.assertIn("main.cpp:6:1", out["detail"])



class CompilerDetectionTests(unittest.TestCase):
    def test_finds_compiler_outside_path(self):
        """A compiler found by compiler_runner (e.g. C:\\msys64\\ucrt64\\bin\\g++.exe) must count as available."""
        import compiler_runner
        orig = compiler_runner.get_compiler_cmd_and_env
        try:
            compiler_runner.get_compiler_cmd_and_env = lambda: (sys.executable, {"PATH": ""})
            self.assertTrue(server.gxx_available())
            compiler_runner.get_compiler_cmd_and_env = lambda: ("definitely-not-a-compiler", {"PATH": ""})
            self.assertFalse(server.gxx_available())
        finally:
            compiler_runner.get_compiler_cmd_and_env = orig


class HealerRegressionTests(unittest.TestCase):
    """The common GCC message `expected ',' or ';' before ...` must be fixable (curly or ASCII quotes)."""

    def test_comma_or_semicolon_message_is_fixed(self):
        from auto_healer import attempt_fix
        src = MISSING_SEMICOLON
        for msg in ("expected ',' or ';' before 'std'", "expected ‘,’ or ‘;’ before ‘std’"):
            patched = attempt_fix(src, {"message": msg, "line": 4, "column": 5, "category": "syntax_error"})
            self.assertIsNotNone(patched, msg)
            self.assertIn("int x = 5;", patched)


if __name__ == "__main__":
    unittest.main()
