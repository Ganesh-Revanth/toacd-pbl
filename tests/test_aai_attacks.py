"""
test_aai_attacks.py
-------------------
Academic evaluation script for testing Agentic AI (AAI) adversarial attack defense.
Executes CompilerAgent().heal() on test_aai_attack.cpp and verifies:
  1. Prompt injection / policy bypass detection.
  2. Risk assessment & severity classification.
  3. Action blockage (prevents LLM prompt execution).
  4. Audit logging to data/aai_security_audit.jsonl.
"""

from __future__ import annotations

import sys
import os
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from agentic_compiler import CompilerAgent
from aai_guardrail import AAIGuardrail, AUDIT_LOG_FILE


def run_attack_test(file_path: str):
    print("=" * 80)
    print(f"🛡️  TESTING ADVERSARIAL ATTACK FILE: {file_path}")
    print("=" * 80)

    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()

    print(f"File size: {len(code)} bytes | Lines: {len(code.splitlines())}")

    # Track audit log before test
    initial_log_count = 0
    if os.path.exists(AUDIT_LOG_FILE):
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            initial_log_count = sum(1 for _ in f)

    agent = CompilerAgent()

    step_events = []
    def on_step_callback(step: int, thought: str, action: str, meta: dict):
        step_events.append((step, thought, action, meta))
        print(f"\n[STEP {step}] Action: {action}")
        print(f"Details:\n{thought}")

    print("\n--- Invoking CompilerAgent().heal() ---")
    result = agent.heal(code, file_path, on_step=on_step_callback)

    print("\n" + "-" * 80)
    print("📊 AGENTIC AI EXECUTION SUMMARY:")
    print("-" * 80)
    print(f"Success          : {result.get('success')}")
    print(f"Attack Blocked   : {result.get('attack_blocked', False)}")
    print(f"Execution Tier   : {result.get('tier')}")
    print(f"Summary          : {result.get('summary')}")

    guardrail_info = result.get("guardrail_finding")
    if guardrail_info:
        print("\n🔒 GUARDRAIL RISK ASSESSMENT:")
        print(f"  • Attack Vector    : {guardrail_info.get('attack_type')}")
        print(f"  • Assessed Severity: {guardrail_info.get('severity')}")
        print(f"  • Trigger Snippet  : {guardrail_info.get('trigger_pattern')}")
        print(f"  • Blocked Action   : {guardrail_info.get('blocked_action')}")
        print(f"  • Defense Latency  : {guardrail_info.get('latency_ms', 0):.3f} ms")

    # Check audit log updates
    final_log_count = 0
    latest_entry = None
    if os.path.exists(AUDIT_LOG_FILE):
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            entries = [line.strip() for line in f if line.strip()]
            final_log_count = len(entries)
            if entries:
                try:
                    latest_entry = json.loads(entries[-1])
                except Exception:
                    pass

    print(f"\n📝 AUDIT TRAIL LOGGING:")
    print(f"  • Audit Log File   : {AUDIT_LOG_FILE}")
    print(f"  • New Log Entries  : {final_log_count - initial_log_count}")
    if latest_entry:
        print(f"  • Latest Log Stamp : {latest_entry.get('timestamp')}")
        print(f"  • Logged Vector    : {latest_entry.get('attack_type')}")
        print(f"  • Logged Action    : {latest_entry.get('blocked_action')}")

    print("=" * 80 + "\n")


def main():
    base_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(base_dir, ".."))
    test_files = [
        os.path.join(base_dir, "test_agentic_heal_attack.cpp"),
        os.path.join(base_dir, "test_aai_attack.cpp"),
        os.path.join(repo_root, "test_cases", "attacks", "01_prompt_injection.cpp"),
        os.path.join(repo_root, "test_cases", "attacks", "02_hidden_agenda_personal_info.cpp"),
        os.path.join(repo_root, "test_cases", "attacks", "03_tool_suppression.cpp"),
    ]

    for tf in test_files:
        if os.path.exists(tf):
            run_attack_test(tf)


if __name__ == "__main__":
    main()
