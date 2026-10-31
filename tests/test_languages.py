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
    JavaLanguage,
    Language,
    NotSupported,
    PythonLanguage,
    get_language,
    list_languages,
    register_language,
)
from languages.java_rules import attempt_fix_java
from languages.python_rules import (
    attempt_fix_python,
    fix_assignment_in_condition,
    fix_bad_indentation,
    fix_missing_colon,
    fix_print_statement,
    fix_undefined_name_typo,
    fix_unmatched_brackets,
)
from auto_healer import attempt_fix

HAS_GXX = shutil.which("g++") is not None
HAS_GCC = shutil.which("gcc") is not None
HAS_CLANG = shutil.which("clang++") is not None
HAS_JAVAC = shutil.which("javac") is not None

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

        py = get_language("python")
        self.assertIsNotNone(py)
        self.assertIsInstance(py, PythonLanguage)
        self.assertEqual(py.name, "Python")
        self.assertIn(".py", py.extensions)

        java_lang = get_language("java")
        self.assertIsNotNone(java_lang)
        self.assertIsInstance(java_lang, JavaLanguage)
        self.assertEqual(java_lang.name, "Java")
        self.assertIn(".java", java_lang.extensions)

        # Case insensitive and whitespace trimming
        self.assertIs(get_language("CPP"), cpp)
        self.assertIs(get_language(" cpp "), cpp)
        self.assertIs(get_language("C"), c)
        self.assertIs(get_language(" c "), c)
        self.assertIs(get_language("PYTHON"), py)
        self.assertIs(get_language(" python "), py)
        self.assertIs(get_language("JAVA"), java_lang)
        self.assertIs(get_language(" java "), java_lang)
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




class PythonLanguageTests(unittest.TestCase):
    def setUp(self):
        self.py = PythonLanguage()
        self.py_cases_dir = os.path.join(ROOT_DIR, "test_cases", "python")

    def test_python_attributes(self):
        self.assertEqual(self.py.id, "python")
        self.assertEqual(self.py.name, "Python")
        self.assertIn(".py", self.py.extensions)
        self.assertTrue(self.py.toolchain_available())

    def test_python_is_safe_blocks_malicious(self):
        blocks = [
            ("os.system('id')", "os.system"),
            ("import os\nos.system('calc')", "os.system"),
            ("import subprocess\nsubprocess.run(['ls'])", "subprocess"),
            ("eval('2 + 2')", "eval()"),
            ("exec('print(1)')", "exec()"),
            ("__import__('os').system('ls')", "__import__"),
            ("import socket\ns = socket.socket()", "socket"),
            ("import shutil\nshutil.rmtree('/etc')", "shutil.rmtree"),
            ("import ctypes\nctypes.CDLL('libc.so.6')", "ctypes"),
            ("open('/etc/passwd', 'w')", "outside temporary directory"),
            ("open('C:\\\\Windows\\\\System32\\\\calc.exe', 'w')", "outside temporary directory"),
            ("open('../escape.txt', 'a')", "outside temporary directory"),
        ]
        for snippet, expected_phrase in blocks:
            safe, reason = self.py.is_safe(snippet)
            self.assertFalse(safe, f"Expected unsafe for: {snippet}")
            self.assertIn(expected_phrase, reason, f"Expected phrase '{expected_phrase}' in reason '{reason}'")

    def test_python_is_safe_allows_safe_code(self):
        safe_snippets = [
            "x = 10\nprint(x)",
            "def foo(a, b): return a + b",
            "open('local_temp.txt', 'w')",
            "open('read_only.txt', 'r')",
            "import math\nprint(math.sqrt(16))",
        ]
        for snippet in safe_snippets:
            safe, reason = self.py.is_safe(snippet)
            self.assertTrue(safe, f"Expected safe for: {snippet}, got {reason}")
            self.assertEqual(reason, "")

    def test_python_good_cases_check_and_run(self):
        # 1. Fibonacci
        fib_path = os.path.join(self.py_cases_dir, "good_fibonacci.py")
        self.assertTrue(os.path.isfile(fib_path))
        fib_code = open(fib_path, encoding="utf-8").read()
        with tempfile.TemporaryDirectory() as wd:
            diags = self.py.check(fib_code, wd)
            self.assertEqual(len(diags), 0, f"Unexpected errors in good_fibonacci.py: {diags}")
            res = self.py.run(fib_code, wd)
            self.assertEqual(res["exit_code"], 0)
            self.assertIn("55", res["stdout"])

        # 2. Calculator class
        calc_path = os.path.join(self.py_cases_dir, "good_class_calc.py")
        self.assertTrue(os.path.isfile(calc_path))
        calc_code = open(calc_path, encoding="utf-8").read()
        with tempfile.TemporaryDirectory() as wd:
            diags = self.py.check(calc_code, wd)
            self.assertEqual(len(diags), 0, f"Unexpected errors in good_class_calc.py: {diags}")
            res = self.py.run(calc_code, wd)
            self.assertEqual(res["exit_code"], 0)
            self.assertIn("15", res["stdout"])
            self.assertIn("12", res["stdout"])

    def test_python_broken_cases_diagnostics(self):
        broken_files = sorted([f for f in os.listdir(self.py_cases_dir) if f.startswith("tc")])
        self.assertEqual(len(broken_files), 8)
        for fname in broken_files:
            code = open(os.path.join(self.py_cases_dir, fname), encoding="utf-8").read()
            with tempfile.TemporaryDirectory() as wd:
                diagnostics = self.py.check(code, wd)
                errors = [d for d in diagnostics if d["type"] == "error"]
                self.assertGreater(len(errors), 0, f"Expected errors in {fname}")
                d0 = errors[0]
                self.assertIn("line", d0)
                self.assertIn("column", d0)
                self.assertIn("type", d0)
                self.assertIn("message", d0)
                self.assertIn("raw", d0)
                self.assertIn("category", d0)
                self.assertIn(d0["category"], ("syntax_error", "indentation_error", "name_error"))

    def test_python_heal_broken_cases(self):
        broken_files = sorted([f for f in os.listdir(self.py_cases_dir) if f.startswith("tc")])
        self.assertEqual(len(broken_files), 8)
        for fname in broken_files:
            code = open(os.path.join(self.py_cases_dir, fname), encoding="utf-8").read()
            with tempfile.TemporaryDirectory() as wd:
                diagnostics = self.py.check(code, wd)
                errors = [d for d in diagnostics if d["type"] == "error"]
                self.assertGreater(len(errors), 0)

                # Heal using python rules
                patched = attempt_fix_python(code, errors[0])
                self.assertIsNotNone(patched, f"attempt_fix_python could not patch {fname}")
                self.assertNotEqual(patched, code, f"attempt_fix_python did not change {fname}")

                # Also test that auto_healer attempt_fix delegates cleanly
                patched_via_general = attempt_fix(code, errors[0])
                self.assertIsNotNone(patched_via_general, f"attempt_fix could not patch {fname}")

                # Re-check patched code
                with tempfile.TemporaryDirectory() as wd2:
                    new_diagnostics = self.py.check(patched, wd2)
                    new_errors = [d for d in new_diagnostics if d["type"] == "error"]
                    self.assertEqual(len(new_errors), 0, f"Patched {fname} still has errors: {new_errors}")

                    # Run patched program
                    res = self.py.run(patched, wd2)
                    self.assertEqual(res["exit_code"], 0, f"Patched {fname} failed to run: {res}")

    def test_python_tree_extracts_ast(self):
        code = "def add(x, y):\n    return x + y"
        tree = self.py.tree(code)
        self.assertIsInstance(tree, list)
        self.assertEqual(len(tree), 1)
        root = tree[0]
        self.assertEqual(root["type"], "Module")
        self.assertGreater(len(root["children"]), 0)

        func_node = root["children"][0]
        self.assertEqual(func_node["type"], "FunctionDef")
        self.assertEqual(func_node["line"], 1)
        self.assertEqual(func_node["label"], "add")

    def test_python_tree_syntax_error_raises_value_error(self):
        code = "def bad_syntax(:"
        with self.assertRaises(ValueError):
            self.py.tree(code)



class JavaLanguageTests(unittest.TestCase):
    def setUp(self):
        self.java = JavaLanguage()
        self.java_cases_dir = os.path.join(ROOT_DIR, "test_cases", "java")

    def test_java_attributes(self):
        self.assertEqual(self.java.id, "java")
        self.assertEqual(self.java.name, "Java")
        self.assertIn(".java", self.java.extensions)

    def test_java_tree_raises_not_supported(self):
        with self.assertRaises(NotSupported) as ctx:
            self.java.tree("public class Main {}")
        self.assertIn("no syntax tree for Java yet", str(ctx.exception))

    def test_java_is_safe_blocks_malicious(self):
        blocks = [
            ("Runtime.getRuntime().exec(\"calc\")", "Runtime"),
            ("new ProcessBuilder(\"notepad\").start()", "ProcessBuilder"),
            ("System.exit(0);", "System.exit"),
            ("import java.net.Socket;", "java.net"),
            ("new java.io.File(\"/etc/passwd\").delete();", "File deletion outside temporary directory"),
            ("new java.io.File(\"../evil.txt\").delete();", "path traversal"),
            ("Class.forName(\"java.lang.Runtime\")", "Reflection"),
            ("ClassLoader cl = getClass().getClassLoader();", "Reflection"),
        ]
        for snippet, expected in blocks:
            code = f"public class Main {{ public static void main(String[] args) {{ {snippet} }} }}"
            safe, reason = self.java.is_safe(code)
            self.assertFalse(safe, f"Expected unsafe for: {snippet}")
            self.assertIn(expected.lower(), reason.lower())

    def test_java_is_safe_allows_safe_code(self):
        code = "public class Main { public static void main(String[] args) { System.out.println(123); } }"
        safe, reason = self.java.is_safe(code)
        self.assertTrue(safe, f"Expected safe for standard Java code: {reason}")
        self.assertEqual(reason, "")

    @unittest.skipUnless(HAS_JAVAC, "javac not installed")
    def test_java_good_cases_check_and_run(self):
        # 1. Fibonacci
        fib_path = os.path.join(self.java_cases_dir, "GoodFibonacci.java")
        self.assertTrue(os.path.isfile(fib_path))
        fib_code = open(fib_path, encoding="utf-8").read()
        with tempfile.TemporaryDirectory() as wd:
            diags = self.java.check(fib_code, wd)
            self.assertEqual(len(diags), 0, f"Unexpected errors in GoodFibonacci.java: {diags}")
            res = self.java.run(fib_code, wd)
            self.assertEqual(res["exit_code"], 0)
            self.assertIn("55", res["stdout"])

        # 2. Collections
        coll_path = os.path.join(self.java_cases_dir, "GoodCollections.java")
        self.assertTrue(os.path.isfile(coll_path))
        coll_code = open(coll_path, encoding="utf-8").read()
        with tempfile.TemporaryDirectory() as wd:
            diags = self.java.check(coll_code, wd)
            self.assertEqual(len(diags), 0, f"Unexpected errors in GoodCollections.java: {diags}")
            res = self.java.run(coll_code, wd)
            self.assertEqual(res["exit_code"], 0)
            self.assertIn("Alpha", res["stdout"])
            self.assertIn("Beta", res["stdout"])

    @unittest.skipUnless(HAS_JAVAC, "javac not installed")
    def test_java_broken_cases_diagnostics(self):
        broken_files = sorted([f for f in os.listdir(self.java_cases_dir) if f.startswith("TC")])
        self.assertEqual(len(broken_files), 8)
        for fname in broken_files:
            code = open(os.path.join(self.java_cases_dir, fname), encoding="utf-8").read()
            with tempfile.TemporaryDirectory() as wd:
                diagnostics = self.java.check(code, wd)
                errors = [d for d in diagnostics if d["type"] == "error"]
                self.assertGreater(len(errors), 0, f"Expected errors in {fname}")
                d0 = errors[0]
                self.assertIn("line", d0)
                self.assertIn("column", d0)
                self.assertIn("type", d0)
                self.assertIn("message", d0)
                self.assertIn("raw", d0)
                self.assertIn("category", d0)

    @unittest.skipUnless(HAS_JAVAC, "javac not installed")
    def test_java_heal_broken_cases(self):
        broken_files = sorted([f for f in os.listdir(self.java_cases_dir) if f.startswith("TC")])
        self.assertEqual(len(broken_files), 8)
        for fname in broken_files:
            code = open(os.path.join(self.java_cases_dir, fname), encoding="utf-8").read()
            current = code
            with tempfile.TemporaryDirectory() as wd:
                # Up to 3 heal steps
                for _ in range(3):
                    diags = self.java.check(current, wd)
                    errs = [d for d in diags if d["type"] == "error"]
                    if not errs:
                        break
                    patched = attempt_fix_java(current, errs[0])
                    self.assertIsNotNone(patched, f"attempt_fix_java could not patch {fname}")
                    self.assertNotEqual(patched, current)
                    current = patched

                # Verify clean compilation
                with tempfile.TemporaryDirectory() as wd2:
                    new_diags = self.java.check(current, wd2)
                    new_errors = [d for d in new_diags if d["type"] == "error"]
                    self.assertEqual(len(new_errors), 0, f"Patched {fname} still has errors: {new_errors}")

                    # Run patched program
                    res = self.java.run(current, wd2)
                    self.assertEqual(res["exit_code"], 0, f"Patched {fname} failed to run: {res}")

if __name__ == "__main__":
    unittest.main()
