"""
agentic_worker.py
-----------------
QThread worker that runs the CompilerAgent asynchronously,
providing real-time thought streams, tool diagnostics, and diffs to the GUI.
"""

from __future__ import annotations

import os
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal

from agentic_compiler import CompilerAgent
from diff_viewer import compute_diff, format_diff_html, has_changes


class AgenticWorker(QThread):
    """
    Asynchronous worker thread for Agentic AI compilation & healing.
    """
    step_progress = pyqtSignal(int, str, str, dict)   # (step, thought, action, meta)
    heal_success  = pyqtSignal(str, str, int)          # (final_code, diff_html, iterations)
    heal_failed   = pyqtSignal(str, list)              # (summary, history)
    error_signal  = pyqtSignal(str)                    # (error_message)

    def __init__(
        self,
        source_code: str,
        file_path: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__()
        self.source_code = source_code
        self.file_path = file_path
        self.api_key = api_key
        self.model = model

    def run(self):
        try:
            agent = CompilerAgent(api_key=self.api_key, model=self.model)

            def _on_step(step: int, thought: str, action: str, meta: dict):
                self.step_progress.emit(step, thought, action, meta)

            result = agent.heal(self.source_code, self.file_path, on_step=_on_step)

            if result["success"]:
                final_code = result["final_code"]
                diff = compute_diff(self.source_code, final_code)
                diff_html = format_diff_html(diff) if has_changes(diff) else "<i>No code changes were required.</i>"
                self.heal_success.emit(final_code, diff_html, result["iterations"])
            else:
                self.heal_failed.emit(result["summary"], result["history"])

        except Exception as exc:
            self.error_signal.emit(str(exc))
