import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from heal_loop import HealWorker
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication


class _MockClassifier:
    def predict(self, msg, ast=""):
        return "syntax_error", 1.0


def main():
    app = QCoreApplication([])
    test_cpp_path = os.path.join(os.path.dirname(__file__), "test_heal.cpp")
    worker = HealWorker(test_cpp_path, _MockClassifier())

    def print_diff(attempt, diff_html):
        print(f"--- Attempt {attempt} Diff ---")

    def compile_clean():
        print("SUCCESS")

    worker.diff_ready.connect(print_diff)
    worker.compile_clean.connect(compile_clean)
    worker._heal()


if __name__ == "__main__":
    main()
