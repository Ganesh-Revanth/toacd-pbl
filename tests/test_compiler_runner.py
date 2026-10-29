import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add src to sys.path so test discovery finds project modules
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_PROJECT_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from compiler_runner import run_cpp_compiler
from error_parser import parse_errors


class TestCompilerRunnerDiagnosticCapture(unittest.TestCase):
    """
    Unit tests for diagnostic capture in src/compiler_runner.py.
    Validates that compiler errors, fatal errors, linker failures,
    and unstructured stderr are properly captured into parser-ready records
    and that linker failures are never treated as CLI success.
    """

    @patch("compiler_runner.subprocess.run")
    @patch("compiler_runner._sanitize_input", return_value=True)
    def test_normal_errors_and_warnings(self, mock_sanitize, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = (
            "test.cpp:5:10: error: expected ';' before '}' token\n"
            "    5 |     int x = 10\n"
            "      |               ^\n"
            "test.cpp:8:5: warning: unused variable 'y' [-Wunused-variable]\n"
        )
        mock_run.return_value = mock_proc

        result = run_cpp_compiler("test.cpp")

        self.assertEqual(len(result), 2)
        # Verify first error
        err0 = result[0]
        self.assertEqual(err0["file"], "test.cpp")
        self.assertEqual(err0["line"], 5)
        self.assertEqual(err0["column"], 10)
        self.assertEqual(err0["type"], "error")
        self.assertEqual(err0["message"], "expected ';' before '}' token")

        # Verify warning
        warn1 = result[1]
        self.assertEqual(warn1["file"], "test.cpp")
        self.assertEqual(warn1["line"], 8)
        self.assertEqual(warn1["column"], 5)
        self.assertEqual(warn1["type"], "warning")
        self.assertIn("unused variable 'y'", warn1["message"])

        # Verify parser readiness
        parsed = parse_errors(result)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0].error_type, "error")
        self.assertEqual(parsed[1].error_type, "warning")

    @patch("compiler_runner.subprocess.run")
    @patch("compiler_runner._sanitize_input", return_value=True)
    def test_fatal_error_missing_header(self, mock_sanitize, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = (
            "test.cpp:1:10: fatal error: nonexistent_header.h: No such file or directory\n"
            "    1 | #include <nonexistent_header.h>\n"
            "      |          ^~~~~~~~~~~~~~~~~~~~~~\n"
            "compilation terminated.\n"
        )
        mock_run.return_value = mock_proc

        result = run_cpp_compiler("test.cpp")

        # Baseline defect check: must NOT return empty list []
        self.assertTrue(len(result) > 0, "run_cpp_compiler must not return [] for fatal error")
        err = result[0]
        self.assertEqual(err["file"], "test.cpp")
        self.assertEqual(err["line"], 1)
        self.assertEqual(err["column"], 10)
        self.assertEqual(err["type"], "error")
        self.assertIn("No such file or directory", err["message"])

        # Verify parser readiness
        parsed = parse_errors(result)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].error_type, "error")

    @patch("compiler_runner.subprocess.run")
    @patch("compiler_runner._sanitize_input", return_value=True)
    def test_linker_undefined_reference(self, mock_sanitize, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = (
            "C:/msys64/ucrt64/bin/ld.exe: C:/temp/cc123.o:test.cpp:5:(.text+0xe): undefined reference to `missing_func()'\n"
            "collect2.exe: error: ld returned 1 exit status\n"
        )
        mock_run.return_value = mock_proc

        result = run_cpp_compiler("test.cpp")

        # Baseline defect check: must NOT return empty list []
        self.assertTrue(len(result) > 0, "run_cpp_compiler must not return [] for linker error")
        err = result[0]
        self.assertEqual(err["type"], "error")
        self.assertIn("missing_func()", err["message"])

        # Verify that linker failure ensures CLI exit code is non-zero (NOT success)
        parsed = parse_errors(result)
        visible_error_count = sum(1 for e in parsed if e.error_type == "error")
        self.assertGreater(
            visible_error_count, 0,
            "Linker error must produce an error_type=='error' so CLI does not report success"
        )

    @patch("compiler_runner.subprocess.run")
    @patch("compiler_runner._sanitize_input", return_value=True)
    def test_linker_multiple_definition_and_cannot_find_lib(self, mock_sanitize, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = (
            "ld.exe: multiple definition of 'foo'; first defined in obj1.o\n"
            "ld.exe: cannot find -lboost_system\n"
            "collect2: error: ld returned 1 exit status\n"
        )
        mock_run.return_value = mock_proc

        result = run_cpp_compiler("test.cpp")
        self.assertTrue(len(result) >= 2)
        self.assertTrue(all(e["type"] == "error" for e in result))
        self.assertTrue(any("multiple definition" in e["message"] for e in result))
        self.assertTrue(any("cannot find -l" in e["message"] for e in result))

    @patch("compiler_runner.subprocess.run")
    @patch("compiler_runner._sanitize_input", return_value=True)
    def test_nonzero_exit_with_unstructured_stderr(self, mock_sanitize, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "g++: error: unrecognized command-line option '-std=c++999'\n"
        mock_run.return_value = mock_proc

        result = run_cpp_compiler("test.cpp")

        self.assertEqual(len(result), 1)
        err = result[0]
        self.assertEqual(err["type"], "error")
        self.assertEqual(err["message"], "g++: error: unrecognized command-line option '-std=c++999'")

        parsed = parse_errors(result)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].error_type, "error")

    @patch("compiler_runner.subprocess.run")
    @patch("compiler_runner._sanitize_input", return_value=True)
    def test_nonzero_exit_with_empty_stderr(self, mock_sanitize, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 139  # SIGSEGV or internal crash
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = run_cpp_compiler("test.cpp")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "error")
        self.assertIn("139", result[0]["message"])

    @patch("compiler_runner.subprocess.run")
    @patch("compiler_runner._sanitize_input", return_value=True)
    def test_clean_compilation_success(self, mock_sanitize, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = run_cpp_compiler("test.cpp")
        self.assertEqual(result, [], "Clean compile must return empty error list")

    @patch("compiler_runner.subprocess.run")
    @patch("compiler_runner._sanitize_input", return_value=True)
    def test_compiler_flags_preserved(self, mock_sanitize, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        run_cpp_compiler("main.cpp")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("-std=c++17", cmd)
        self.assertIn("-static", cmd)
        self.assertIn("-static-libgcc", cmd)
        self.assertIn("-static-libstdc++", cmd)
        self.assertIn("-o", cmd)
        self.assertTrue(any(arg.endswith(("a.exe", "a.out")) for arg in cmd))

    def test_sanitizer_preservation(self):
        import tempfile
        # Without mocking sanitize, pass source code that has system() in an isolated temp dir outside repo
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "unsafe_temp.cpp")
            with open(test_file, "w") as f:
                f.write('int main() { system("whoami"); return 0; }\n')
            result = run_cpp_compiler(test_file)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["type"], "error")
            self.assertIn("Security Error", result[0]["message"])

    @patch("compiler_runner.subprocess.run", side_effect=FileNotFoundError("g++ not found"))
    @patch("compiler_runner._sanitize_input", return_value=True)
    def test_compiler_not_found(self, mock_sanitize, mock_run):
        result = run_cpp_compiler("test.cpp")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "error")
        self.assertIn("g++ compiler not found", result[0]["message"])


if __name__ == "__main__":
    unittest.main()
