"""
Unit test verifying that all numbers quoted across project documentation
files match canonical ground-truth data in results/.
"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_documentation_numbers_match_results():
    """Run scripts/check_doc_numbers.py and assert exit code 0."""
    script_path = ROOT / "scripts" / "check_doc_numbers.py"
    res = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
    assert res.returncode == 0, f"check_doc_numbers.py failed:\n{res.stdout}\n{res.stderr}"

