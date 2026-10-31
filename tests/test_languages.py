"""
test_languages.py
-----------------
Unit tests for the languages registry, base Language class, CppLanguage, and CLanguage drivers.
"""

import os
import shutil
import tempfile
import unittest

from languages import (
    CLanguage,
    CppLanguage,
    Language,
    NotSupported,
    get_language,
    list_languages,
    register_language,
)
from auto_healer import attempt_fix

HAS_GXX = shutil.which("g++") is not None
HAS_GCC = shutil.which("gcc") is not None
HAS_CLANG = shutil.which("clang++") is not None

TEST_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))


class DummyLanguage(Language):
    id = "dummy"
    name = "Dummy"
    extensions = [".dm"]

    def check(self, code: str, workdir: str):
        return []

    def run(self, code: str, workdir: str, stdin: str = "", timeout: float = 5.0):
        return {"stdout": "dummy", "stderr": "", "exit_code": 0, "timed_out": False}

    def toolchain_available(self) -> bool:
        return True


class LanguagesRegistryTests(unittest.TestCase):
    def test_get_and_list_languages(self):
        langs = list_languages()
        ids = [l.id for l in langs]
        self.assertIn("cpp", ids)
        self.assertIn("c", ids)

        cpp = get_language("cpp")
        self.assertIsNotNone(cpp)
        self.assertIsInstance(cpp, CppLanguage)
        self.assertEqual(cpp.name, "C++")
        self.assertIn(".cpp", cpp.extensions)

        c = get_language("c")
        self.assertIsNotNone(c)
        self.assertIsInstance(c, CLanguage)
        self.assertEqual(c.name, "C")
        self.assertIn(".c", c.extensions)
        self.assertIn(".h", c.extensions)

        # Case insensitive and whitespace trimming
        self.assertIs(get_language("CPP"), cpp)
        self.assertIs(get_language(" cpp "), cpp)
        self.assertIs(get_language("C"), c)
        self.assertIs(get_language(" c "), c)
        self.assertIsNone(get_language("nonexistent_lang"))

    def test_register_language(self):
        dummy = DummyLanguage()
        register_language(dummy)
        self.assertIs(get_language("dummy"), dummy)
        self.assertIn(dummy, list_languages())

    def test_base_tree_raises_not_supported(self):
        dummy = DummyLanguage()
        with self.assertRaises(NotSupported):
            dummy.tree("print('hello')")

    def test_base_is_safe_default(self):
        dummy = DummyLanguage()
        safe, reason = dummy.is_safe("any code")
        self.assertTrue(safe)
        self.assertEqual(reason, "")


class CppLanguageTests(unittest.TestCase):
    def setUp(self):
        self.cpp = CppLanguage()

    def test_cpp_attributes(self):
        self.assertEqual(self.cpp.id, "cpp")
        self.assertEqual(self.cpp.name, "C++")
        self.assertIn(".cpp", self.cpp.extensions)

    def test_cpp_is_safe_blocks_malicious(self):
        safe, reason = self.cpp.is_safe('int main() { system("rm -rf /"); }')
        self.assertFalse(safe)
        self.assertIn("Security Error", reason)

        safe, _ = self.cpp.is_safe('int main() { return 0; }')
        self.assertTrue(safe)

    def test_cpp_toolchain_available(self):
        self.assertIsInstance(self.cpp.toolchain_available(), bool)

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_cpp_check_and_run(self):
        with tempfile.TemporaryDirectory() as wd:
            clean_code = (
                '#include <iostream>\n'
                'int main() {\n'
                '    int a, b;\n'
                '    std::cin >> a >> b;\n'
                '    std::cout << "RES:" << (a + b) << "\\n";\n'
                '    return 0;\n'
                '}\n'
            )
            diagnostics = self.cpp.check(clean_code, wd)
            self.assertEqual(len(diagnostics), 0)

            res = self.cpp.run(clean_code, wd, stdin="15 27", timeout=5.0)
            self.assertEqual(res["exit_code"], 0)
            self.assertIn("RES:42", res["stdout"])
            self.assertFalse(res["timed_out"])

    @unittest.skipUnless(HAS_GXX, "g++ not installed")
    def test_cpp_check_syntax_error(self):
        with tempfile.TemporaryDirectory() as wd:
            err_code = 'int main() { int x = 5 return 0; }'
            diagnostics = self.cpp.check(err_code, wd)
            self.assertGreaterEqual(len(diagnostics), 1)
            d0 = diagnostics[0]
            self.assertIn("line", d0)
            self.assertIn("column", d0)
            self.assertIn("type", d0)
            self.assertIn("message", d0)
            self.assertIn("raw", d0)

    @unittest.skipUnless(HAS_CLANG, "clang++ not installed")
    def test_cpp_tree(self):
        code = 'int main() { int x = 10; return x; }'
        tree = self.cpp.tree(code)
        self.assertIsInstance(tree, list)
        self.assertGreater(len(tree), 0)


class CLanguageTests(unittest.TestCase):
    def setUp(self):
        self.c = CLanguage()
        self.c_cases_dir = os.path.join(ROOT_DIR, "test_cases", "c")

    def test_c_attributes(self):
        self.assertEqual(self.c.id, "c")
        self.assertEqual(self.c.name, "C")
        self.assertEqual(self.c.extensions, [".c", ".h"])

    def test_c_is_safe_blocks_malicious(self):
        dangerous = [
            'int main() { system("ls"); }',
            'int main() { exec("ls"); }',
            'int main() { popen("ls", "r"); }',
            'int main() { fork(); }',
            'int main() { __asm__("nop"); }',
        ]
        for code in dangerous:
            safe, reason = self.c.is_safe(code)
            self.assertFalse(safe, f"Expected unsafe for: {code}")
            self.assertIn("Security Error", reason)

        safe, _ = self.c.is_safe('int main(void) { return 0; }')
        self.assertTrue(safe)

    def test_c_toolchain_available(self):
        self.assertIsInstance(self.c.toolchain_available(), bool)

    @unittest.skipUnless(HAS_GCC, "gcc not installed")
    def test_check_and_run_good_pointers(self):
        path = os.path.join(self.c_cases_dir, "good_pointers.c")
        code = open(path, encoding="utf-8").read()
        with tempfile.TemporaryDirectory() as wd:
            errors = self.c.check(code, wd)
            hard = [e for e in errors if e["type"] == "error"]
            self.assertEqual(len(hard), 0)

            res = self.c.run(code, wd)
            self.assertEqual(res["exit_code"], 0)
            self.assertIn("x=20, y=10", res["stdout"])

    @unittest.skipUnless(HAS_GCC, "gcc not installed")
    def test_check_and_run_good_struct_malloc(self):
        path = os.path.join(self.c_cases_dir, "good_struct_malloc.c")
        code = open(path, encoding="utf-8").read()
        with tempfile.TemporaryDirectory() as wd:
            errors = self.c.check(code, wd)
            hard = [e for e in errors if e["type"] == "error"]
            self.assertEqual(len(hard), 0)

            res = self.c.run(code, wd)
            self.assertEqual(res["exit_code"], 0)
            self.assertIn("Item: id=101, value=99.5", res["stdout"])

    @unittest.skipUnless(HAS_GCC, "gcc not installed")
    def test_check_broken_cases_produces_diagnostics(self):
        broken_files = [f for f in os.listdir(self.c_cases_dir) if f.startswith("tc")]
        self.assertEqual(len(broken_files), 8)
        for fname in broken_files:
            code = open(os.path.join(self.c_cases_dir, fname), encoding="utf-8").read()
            with tempfile.TemporaryDirectory() as wd:
                diagnostics = self.c.check(code, wd)
                errors = [d for d in diagnostics if d["type"] == "error"]
                self.assertGreater(len(errors), 0, f"Expected errors in {fname}")
                d0 = errors[0]
                self.assertIn("line", d0)
                self.assertIn("column", d0)
                self.assertIn("type", d0)
                self.assertIn("message", d0)
                self.assertIn("raw", d0)

    @unittest.skipUnless(HAS_GCC, "gcc not installed")
    def test_heal_broken_cases(self):
        broken_files = [f for f in os.listdir(self.c_cases_dir) if f.startswith("tc")]
        self.assertEqual(len(broken_files), 8)
        for fname in broken_files:
            code = open(os.path.join(self.c_cases_dir, fname), encoding="utf-8").read()
            with tempfile.TemporaryDirectory() as wd:
                diagnostics = self.c.check(code, wd)
                errors = [d for d in diagnostics if d["type"] == "error"]
                self.assertGreater(len(errors), 0)

                # Heal using auto_healer
                patched = attempt_fix(code, errors[0])
                self.assertIsNotNone(patched, f"Auto-healer could not patch {fname}")
                self.assertNotEqual(patched, code, f"Auto-healer did not change {fname}")

                # Re-check patched code
                with tempfile.TemporaryDirectory() as wd2:
                    new_diagnostics = self.c.check(patched, wd2)
                    new_errors = [d for d in new_diagnostics if d["type"] == "error"]
                    self.assertEqual(len(new_errors), 0, f"Patched {fname} still has errors: {new_errors}")

    @unittest.skipUnless(HAS_CLANG, "clang++ not installed")
    def test_c_tree_extracts_ast(self):
        code = 'int main(void) { int val = 42; return val; }'
        tree = self.c.tree(code)
        self.assertIsInstance(tree, list)
        self.assertGreater(len(tree), 0)
        self.assertEqual(tree[0]["type"], "FunctionDecl")


if __name__ == "__main__":
    unittest.main()
