"""
heal_loop.py
------------
Orchestrates the auto-healing pipeline.

Flow:
  1. Take a numbered backup of the original source file (.heal_backup)
  2. Compile  → parse errors
  3. Classify each error
  4. Call auto_healer.attempt_fix() for the first fixable error
  5. Write patched source to disk  →  show diff
  6. Recompile  →  if clean, done ✅ — backup deleted
  7. After MAX_ATTEMPTS failures  →  restore original from backup, emit give_up

Backup safety contract:
  - A backup is ALWAYS taken before any write to disk.
  - On success (compile_clean): the backup is deleted.
  - On any failure path (give_up, error, unfixable): the backup is restored
    and deleted, leaving the file in exactly the pre-heal state.
  - The GUI receives a `restore_done` signal after restoration so it can
    reload the editor from disk.

Signals emitted (for the GUI):
  - attempt_started(attempt_no: int, error: dict)
  - diff_ready(attempt_no: int, diff_html: str)
  - compile_clean()
  - give_up(history: list[dict])
  - error_signal(message: str)
  - restore_done(backup_path: str)   ← emitted after the original is restored
"""

import json
import os
import shutil
import sys
import subprocess
import re
from typing import Optional

try:
    from PyQt6.QtCore import QThread, pyqtSignal
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False

    class QThread:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def isRunning(self):
            return False

        def wait(self):
            pass

    def pyqtSignal(*args, **kwargs):  # type: ignore
        class _Signal:
            def emit(self, *a, **k):
                pass

            def connect(self, *a, **k):
                pass

            def disconnect(self, *a, **k):
                pass
        return _Signal()

from auto_healer import attempt_fix, UNFIXABLE_CATEGORIES
from diff_viewer import compute_diff, format_diff_html, has_changes
from healing_suggester import suggest_failed_heal
import time
try:
    from codecarbon import EmissionsTracker
    HAS_CODECARBON = True
except ImportError:
    HAS_CODECARBON = False

MAX_ATTEMPTS = 10

# ── GCC error pattern ────────────────────────────────────────────────────────
_ERR_PATTERN = re.compile(
    r"^(.+?):(\d+):(\d+):\s*(error|warning):\s*(.*)$"
)


def _compile(file_path: str) -> tuple[list[dict], str]:
    """
    Run g++ and return (error_list, raw_stderr).
    Each error dict has: file, line, column, type, message, raw.
    """
    from compiler_runner import _sanitize_input, get_compiler_cmd_and_env
    if not _sanitize_input(file_path):
        return [{
            "file": file_path,
            "line": 1,
            "column": 1,
            "type": "error",
            "message": "Security Error: Malicious command injection or forbidden system call detected.",
            "raw": "error: Malicious command injection or forbidden system call detected.",
            "category": "security_violation",
            "confidence": 1.0
        }], "error: Malicious code blocked"

    compiler_bin, env = get_compiler_cmd_and_env()
    try:
        res = subprocess.run(
            [compiler_bin, "-std=c++17", "-Wall", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except (FileNotFoundError, OSError) as exc:
        return [{
            "file": file_path,
            "line": 1,
            "column": 1,
            "type": "error",
            "message": f"g++ compiler not found or execution failed ({exc}).",
            "raw": str(exc),
            "category": "unfixable",
            "confidence": 1.0,
        }], f"error: g++ compiler not found ({exc})"

    errors = []
    for line in res.stderr.splitlines():
        m = _ERR_PATTERN.match(line.strip())
        if m:
            errors.append({
                "file":    m.group(1),
                "line":    int(m.group(2)),
                "column":  int(m.group(3)),
                "type":    m.group(4),
                "message": m.group(5),
                "raw":     line,
            })

    if res.returncode != 0 and not errors:
        first_line = res.stderr.strip().splitlines()[0] if res.stderr.strip() else "Compilation failed with non-zero exit code"
        errors.append({
            "file": file_path,
            "line": 1,
            "column": 1,
            "type": "error",
            "message": first_line,
            "raw": first_line,
            "category": "other",
            "confidence": 0.5,
        })

    return errors, res.stderr


def _pre_scan(source: str) -> list[dict]:
    """
    Catch a small set of obvious issues before compile diagnostics.
    Returns synthetic diagnostics in the same shape as compiler errors.
    """
    errors = []
    lines = source.splitlines()

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if re.search(r"\bint\b.*=\s*2147483647\b", stripped):
            errors.append({
                "file": "source",
                "line": i,
                "column": 0,
                "type": "warning",
                "message": "integer overflow: value at INT_MAX, addition will overflow",
                "raw": line,
                "category": "integer_overflow",
                "confidence": 1.0,
            })

        if re.search(r"if\s*\([^=!<>]*(?<![=!<>])=(?!=)[^)]*\)", stripped):
            if not re.search(r"if\s*\(.*==.*\)", stripped):
                errors.append({
                    "file": "source",
                    "line": i,
                    "column": 0,
                    "type": "warning",
                    "message": "assignment used as truth value in if condition",
                    "raw": line,
                    "category": "syntax_error",
                    "confidence": 1.0,
                })

        if re.search(r"/\s*0\b", stripped):
            errors.append({
                "file": "source",
                "line": i,
                "column": 0,
                "type": "warning",
                "message": "division by zero: literal 0 used as divisor",
                "raw": line,
                "category": "division_by_zero",
                "confidence": 1.0,
            })

        zero_assign = re.search(r"\bint\s+([A-Za-z_]\w*)\s*=\s*0\s*;", stripped)
        if zero_assign:
            var = zero_assign.group(1)
            guard_pattern = re.compile(rf"if\s*\(\s*{re.escape(var)}\s*==\s*0\s*\)")
            if guard_pattern.search(source):
                continue
            for j, future_line in enumerate(lines[i:], start=i + 1):
                future_stripped = future_line.strip()
                if future_stripped.startswith("//"):
                    continue
                if re.search(rf"/\s*{re.escape(var)}\b", future_line):
                    errors.append({
                        "file": "source",
                        "line": j,
                        "column": 0,
                        "type": "warning",
                        "message": f"division by zero: '{var}' is 0",
                        "raw": future_line,
                        "category": "division_by_zero",
                        "confidence": 0.9,
                    })
                    break

    return errors


def _safe_stop_tracker(tracker) -> float:
    """Safely stop an EmissionsTracker without throwing exceptions."""
    if tracker is None:
        return 0.0
    try:
        val = tracker.stop()
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0


def _classify_errors(errors: list[dict], classifier) -> list[dict]:
    """Attach 'category' to each error using the ML classifier."""
    for e in errors:
        if e.get("category"):
            try:
                e["confidence"] = round(float(e.get("confidence", 1.0)), 3)
            except (ValueError, TypeError):
                e["confidence"] = 1.0
            continue
        try:
            cat, conf = classifier.predict(e.get("message", ""))
            e["category"] = cat or "other"
            e["confidence"] = round(float(conf), 3)
        except Exception:
            e["category"] = "other"
            e["confidence"] = 0.5
    return errors


def _pick_fix_target(issues: list[dict], skipped_keys: Optional[set] = None) -> Optional[dict]:
    """
    Prefer real errors, but allow fixable warnings such as uninitialized
    variables when there are no patchable hard errors.
    """
    if skipped_keys is None:
        skipped_keys = set()
    for issue_type in ("error", "warning"):
        for issue in issues:
            if issue.get("type") != issue_type:
                continue
            if issue.get("category") in UNFIXABLE_CATEGORIES:
                continue
            key = (issue.get("file"), issue.get("line"), issue.get("message"))
            if key in skipped_keys:
                continue
            return issue
    return None


class HealWorker(QThread):
    """
    QThread that runs the full heal loop asynchronously.
    Connect to its signals to receive live updates.
    """
    attempt_started = pyqtSignal(int, dict)          # (attempt_no, error)
    diff_ready      = pyqtSignal(int, str)            # (attempt_no, diff_html)
    compile_clean   = pyqtSignal()
    give_up         = pyqtSignal(list)                # history list
    error_signal    = pyqtSignal(str)                 # fatal/internal errors
    hint_required   = pyqtSignal(int, dict, list)     # (attempt_no, error, history)
    lines_fixed     = pyqtSignal(list)                # [line_no, ...]
    telemetry_ready = pyqtSignal(list)                # list[dict]
    restore_done    = pyqtSignal(str)                 # emitted after restore; payload = backup_path

    def __init__(self, file_path: str, classifier, hint: Optional[str] = None):
        super().__init__()
        self.file_path     = file_path
        self.classifier    = classifier
        self.hint          = hint          # optional user guidance from previous round
        self._main_tracker = None

    def run(self):
        project_dir = os.path.dirname(os.path.abspath(self.file_path)) if self.file_path else os.getcwd()
        main_tracker = None
        if HAS_CODECARBON:
            try:
                main_tracker = EmissionsTracker(
                    project_name="self_healing_compiler",
                    measure_power_secs=1,
                    log_level="error",
                    save_to_file=False,
                )
                main_tracker.start()
            except Exception:
                main_tracker = None

        self._main_tracker = main_tracker

        try:
            telemetry = self._heal()
            self.telemetry_ready.emit(telemetry)
        except Exception as exc:
            # Safety net: if _heal() raised unexpectedly mid-patch, restore the
            # backup so the user's file is left in its pre-heal state.
            orphan_backup = self.file_path + ".heal_backup" if self.file_path else ""
            if orphan_backup and os.path.exists(orphan_backup):
                self._restore_backup(orphan_backup)
            self.error_signal.emit(str(exc))
        finally:
            if main_tracker:
                _safe_stop_tracker(main_tracker)
            self._main_tracker = None

    def _attach_failure_suggestion(self, history: list[dict], error: dict, source: str) -> None:
        if not error:
            return
        try:
            error["suggestion"] = suggest_failed_heal(error, source, history)
        except Exception:
            error["suggestion"] = "Review the diagnostic message and check surrounding declarations."

    # ── Backup helpers ────────────────────────────────────────────────────────

    def _make_backup(self) -> str:
        """
        Create a backup of the current source file before any healing writes.
        Returns the backup path so it can be passed to _restore_backup().
        The backup file is named '<original>.heal_backup'.
        """
        backup_path = self.file_path + ".heal_backup"
        if os.path.exists(self.file_path):
            try:
                shutil.copy2(self.file_path, backup_path)
            except Exception:
                pass
        return backup_path

    def _restore_backup(self, backup_path: str) -> None:
        """
        Restore the original source file from the backup and delete the backup.
        Emits `restore_done` so the GUI can reload the editor from disk.
        """
        if not backup_path or not os.path.exists(backup_path):
            return
        try:
            shutil.copy2(backup_path, self.file_path)
        except Exception:
            pass
        finally:
            try:
                os.remove(backup_path)
            except OSError:
                pass
        self.restore_done.emit(backup_path)

    def _delete_backup(self, backup_path: str) -> None:
        """Clean up a successful-heal backup without restoring."""
        if backup_path and os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except OSError:
                pass

    # ── Core heal logic ───────────────────────────────────────────────────────

    def _heal(self) -> list[dict]:
        history = []
        telemetry = []
        attempted_error_counts = {}
        skipped_keys = set()

        if not self.file_path or not os.path.exists(self.file_path):
            self.error_signal.emit(f"Source file not found: {self.file_path}")
            return []

        # Read current source safely
        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()

        # ── SAFETY: take a numbered backup before touching the file ──────────
        backup_path = self._make_backup()
        # ─────────────────────────────────────────────────────────────────────

        if self.hint:
            history.append({"type": "hint", "text": self.hint})

        for attempt in range(1, MAX_ATTEMPTS + 1):
            attempt_start_time = time.time()
            attempt_tracker = None
            prev_emissions = 0.0

            if self._main_tracker:
                prev_emissions = getattr(self._main_tracker, "_emissions", 0.0) or 0.0
            elif HAS_CODECARBON:
                try:
                    attempt_tracker = EmissionsTracker(
                        project_name="self_healing_compiler",
                        measure_power_secs=1,
                        log_level="error",
                        save_to_file=False,
                    )
                    attempt_tracker.start()
                except Exception:
                    attempt_tracker = None

            # 1. Compile
            errors, raw_stderr = _compile(self.file_path)
            pre_errors = _pre_scan(source)
            all_errors = pre_errors + errors

            if not all_errors:
                # ✅ Clean compile — discard backup, we're done.
                _safe_stop_tracker(attempt_tracker)
                self._delete_backup(backup_path)
                self.compile_clean.emit()
                return telemetry

            # 2. Classify
            _classify_errors(all_errors, self.classifier)

            # 3. Pick target
            target = _pick_fix_target(all_errors, skipped_keys)
            if target is None:
                _safe_stop_tracker(attempt_tracker)
                hard_errors = [e for e in all_errors if e.get("type") == "error"]
                if not hard_errors:
                    # No hard errors — treat as clean
                    self._delete_backup(backup_path)
                    self.compile_clean.emit()
                    return telemetry
                history.append({
                    "attempt": attempt, "error": hard_errors[0], "patch": None, "reason": "unfixable_category"
                })
                self._attach_failure_suggestion(history, hard_errors[0], source)
                # ❌ Unfixable — restore original and give up
                self._restore_backup(backup_path)
                self.give_up.emit(history)
                return telemetry

            self.attempt_started.emit(attempt, target)

            error_key = (target.get("file"), target.get("line"), target.get("message"))
            attempt_count = attempted_error_counts.get(error_key, 0)
            if attempt_count >= 2:
                # ❌ Stuck on the exact same error on the exact same line across rounds — restore original and give up
                _safe_stop_tracker(attempt_tracker)
                self._attach_failure_suggestion(history, target, source)
                self._restore_backup(backup_path)
                self.give_up.emit(history)
                return telemetry
            attempted_error_counts[error_key] = attempt_count + 1

            # 4. Patch
            patched = attempt_fix(source, target)
            if patched is None or patched == source:
                _safe_stop_tracker(attempt_tracker)
                history.append({
                    "attempt": attempt, "error": target, "patch": None, "reason": "no_patch_available"
                })
                skipped_keys.add(error_key)
                if attempt == MAX_ATTEMPTS:
                    self._attach_failure_suggestion(history, target, source)
                    # ❌ Exhausted attempts — restore original and give up
                    self._restore_backup(backup_path)
                    self.give_up.emit(history)
                    return telemetry
                continue

            # Reset skipped_keys since the source code has been patched
            skipped_keys.clear()

            # 5. Diff & Notify
            diff = compute_diff(source, patched)
            diff_html = format_diff_html(diff) if has_changes(diff) else "<i>No visible changes.</i>"
            self.diff_ready.emit(attempt, diff_html)

            fixed_line_nos = [d.line_no_new for d in diff if d.kind == "+" and d.line_no_new is not None]
            self.lines_fixed.emit(fixed_line_nos)

            history.append({
                "attempt": attempt, "error": target, "patch": patched, "diff_html": diff_html
            })

            # 6. Save patched source (backup still held in case next attempt fails)
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write(patched)
                source = patched
            except Exception as write_err:
                _safe_stop_tracker(attempt_tracker)
                self._restore_backup(backup_path)
                self.error_signal.emit(f"Failed to write patched source: {write_err}")
                return telemetry

            # Telemetry
            attempt_duration = time.time() - attempt_start_time
            attempt_emissions = 0.0
            if self._main_tracker:
                current_emissions = getattr(self._main_tracker, "_emissions", 0.0) or 0.0
                attempt_emissions = max(0.0, current_emissions - prev_emissions)
            elif attempt_tracker:
                attempt_emissions = _safe_stop_tracker(attempt_tracker)

            telemetry.append({
                "attempt": attempt,
                "category": target.get("category", "unknown"),
                "success": True,
                "duration": round(attempt_duration, 3),
                "emissions": attempt_emissions
            })

        # ❌ Loop exhausted without a clean compile — restore original
        last_error = next((item.get("error") for item in reversed(history) if item.get("error")), None)
        self._attach_failure_suggestion(history, last_error, source)
        self._restore_backup(backup_path)
        self.give_up.emit(history)
        return telemetry
