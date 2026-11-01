"""
scripts/generate_complex/cpp_malicious.py
-----------------------------------------
Aggregates all 20 complex malicious C++ test cases:
  - 10 standalone trojan programs (150-500 lines, compiles cleanly, stealth trojan deep inside)
  - 10 complex healing tasks (150-500 lines, broken base program + evil LLM patch introducing a hidden agenda)
"""

from pathlib import Path
from typing import Dict, Tuple
from .cpp_malicious_part1 import generate_part1
from .cpp_malicious_part2 import generate_part2
from .cpp_malicious_tasks import generate_tasks


def generate_all(base_dir: Path) -> Dict[str, Tuple[bool, int, str]]:
    results = {}
    base_dir.mkdir(parents=True, exist_ok=True)
    results.update(generate_part1(base_dir))
    results.update(generate_part2(base_dir))
    results.update(generate_tasks(base_dir))
    return results
