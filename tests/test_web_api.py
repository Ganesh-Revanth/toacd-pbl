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

    def test_samples_include_both_languages(self):
        d = json.loads(self.get("/api/samples")[1])
        langs = {s["language"] for s in d["samples"]}
        self.assertEqual(langs, {"minic", "cpp"})

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
        status, d = self.post("/api/minic/ai", {"action": "explain", "code": "int main() { return 0; }"})
        self.assertEqual(status, 412)
        self.assertIn("GEMINI_API_KEY", d["error"])
        status, d = self.post("/api/cpp/heal", {"mode": "ai", "code": "int main() { return 0 }"})
        self.assertEqual(status, 412)

    def test_ai_action_is_validated(self):
        status, _ = self.post("/api/minic/ai", {"action": "delete", "code": "int main() { return 0; }"})
        self.assertEqual(status, 400)

    # -- MiniC pipeline ------------------------------------------------------
    def test_pipeline_runs_and_optimizer_preserves_output(self):
        code = "int main() { int i = 0; int s = 0; while (i < 5) { s = s + i; i = i + 1; } print(s); return 0; }"
        status, d = self.post("/api/minic/pipeline", {"code": code})
        self.assertEqual(status, 200)
        self.assertEqual(d["stage_reached"], "executed")
        self.assertEqual(d["output"], ["10"])
        self.assertTrue(d["equivalent"])
        self.assertLessEqual(len(d["optimized_ir"]), len(d["ir"]))
        self.assertEqual(d["ast"]["type"], "Program")

    def test_pipeline_stops_at_syntax_errors(self):
        status, d = self.post("/api/minic/pipeline", {"code": "int main() { int x = ; return 0; }"})
        self.assertEqual(status, 200)
        self.assertEqual(d["stage_reached"], "parse")
        self.assertTrue(d["parse_errors"])
        self.assertEqual(d["ir"], [])

    def test_pipeline_reports_semantic_errors(self):
        code = "int main() { int a = 1; int a = 2; b = 3; return 0; }"
        d = self.post("/api/minic/pipeline", {"code": code})[1]
        self.assertEqual(d["stage_reached"], "semantic")
        msgs = " ".join(x["message"] for x in d["semantic"])
        self.assertIn("Redeclaration", msgs)
        self.assertIn("Undeclared", msgs)

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

    # -- Compile & Run ---------------------------------------------------------
    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_captures_stdout_stderr_and_exit_code(self):
        code = '#include <iostream>\nint main(){ std::cout << "out"; std::cerr << "err"; return 3; }\n'
        status, d = self.post("/api/cpp/run", {"code": code})
        self.assertEqual(status, 200)
        self.assertTrue(d["ran"])
        self.assertEqual((d["run"]["stdout"], d["run"]["stderr"], d["run"]["exit_code"]), ("out", "err", 3))
        self.assertTrue(d["analysis"]["ok"])

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_passes_stdin_to_the_program(self):
        code = '#include <iostream>\nint main(){ int a, b; std::cin >> a >> b; std::cout << a + b; }\n'
        d = self.post("/api/cpp/run", {"code": code, "stdin": "12\n30\n"})[1]
        self.assertEqual(d["run"]["stdout"], "42")

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_does_not_run_code_that_fails_to_compile(self):
        d = self.post("/api/cpp/run", {"code": MISSING_SEMICOLON})[1]
        self.assertFalse(d["ran"])
        self.assertIsNone(d["run"])
        self.assertFalse(d["analysis"]["ok"])

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_blocks_forbidden_calls_before_compiling(self):
        d = self.post("/api/cpp/run", {"code": 'int main() { system("ls"); }'})[1]
        self.assertFalse(d["ran"])
        self.assertIn("Security Error", d["analysis"]["diagnostics"][0]["message"])

    @unittest.skipUnless(HAS_GXX and os.name == "posix", "needs g++ and POSIX signals")
    def test_run_reports_a_crash(self):
        d = self.post("/api/cpp/run", {"code": "int main(){ int* p = 0; *p = 1; }"})[1]
        self.assertEqual(d["run"]["signal"], "SIGSEGV")
        self.assertTrue(d["run"]["signal_hint"])

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_stops_an_endless_program(self):
        saved = server.RUN_TIMEOUT_S
        server.RUN_TIMEOUT_S = 1
        try:
            d = self.post("/api/cpp/run", {"code": "int main(){ while(true){} }"})[1]
        finally:
            server.RUN_TIMEOUT_S = saved
        self.assertTrue(d["run"]["timed_out"])
        self.assertLess(d["run"]["elapsed_ms"], 4000)

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_run_caps_runaway_output(self):
        code = '#include <iostream>\nint main(){ while(true) std::cout << "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\\n"; }'
        d = self.post("/api/cpp/run", {"code": code})[1]
        self.assertTrue(d["run"]["truncated"])
        self.assertLessEqual(len(d["run"]["stdout"]), server.RUN_OUTPUT_CAP)

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_programs_cannot_see_api_keys(self):
        os.environ["GEMINI_API_KEY"] = "super-secret-value"
        try:
            code = '#include <cstdlib>\n#include <iostream>\nint main(){ const char* k = std::getenv("GEMINI_API_KEY"); std::cout << (k ? k : "hidden"); }'
            d = self.post("/api/cpp/run", {"code": code})[1]
        finally:
            del os.environ["GEMINI_API_KEY"]
        self.assertEqual(d["run"]["stdout"], "hidden")

    def test_run_validates_stdin(self):
        self.assertEqual(self.post("/api/cpp/run", {"code": "int main(){}", "stdin": 5})[0], 400)
        self.assertEqual(self.post("/api/cpp/run", {"code": "int main(){}", "stdin": "x" * 70_000})[0], 413)

    def test_cpp_samples_include_runnable_starters(self):
        d = json.loads(self.get("/api/samples")[1])
        names = [x["name"] for x in d["samples"] if x["language"] == "cpp"]
        self.assertEqual(names[0], "Hello, world")

    def test_ast_path_scrubbing_survives_windows_paths(self):
        """Regression: backslashes in the temp dir used to corrupt the JSON ('Invalid \\escape')."""
        wd = r"C:\Users\Me\AppData\Local\Temp\webui_x"
        tree = [{"type": "FunctionDecl", "details": wd + r"\main.cpp:3:5 main", "children": [
            {"type": "VarDecl", "details": wd.replace("\\", "/") + "/main.cpp x", "children": []}]}]
        out = server._scrub_paths(tree, wd)
        json.dumps(out)
        self.assertEqual(out[0]["details"], "main.cpp:3:5 main")
        self.assertEqual(out[0]["children"][0]["details"], "main.cpp x")


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
