"""
Complex broken Python program with control flow and unclosed string faults.
Contains 3-5 distinct compilation/syntax errors for the self-healing benchmark.
"""

from typing import List, Dict


class ConfigurationSetting:
    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value






class ConfigFileWatcher:
    def __init__(self, file_path: str = "app.conf"):
        self.file_path = file_path
        self.modified_counter = 0

    def mark_modified(self) -> None:
        self.modified_counter += 1

    def get_count(self) -> int:
        return self.modified_counter


class ConfigValidationSchema:
    def __init__(self, schema_name: str):
        self.schema_name = schema_name
        self.required_keys: List[str] = ["database.url", "redis.host"]

    def validate_keys(self, keys: List[str]) -> bool:
        return all(k in keys for k in self.required_keys)


class ConfigDiffGenerator:
    def __init__(self):
        self.diff_records: List[str] = []

    def compute_diff(self, old_cfg: Dict[str, str], new_cfg: Dict[str, str]) -> List[str]:
        diffs = []
        for k in new_cfg:
            if k not in old_cfg:
                diffs.append(f"Added {k}")
        return diffs


class ConfigReloadWatchdog:
    def __init__(self, check_interval_sec: float = 5.0):
        self.check_interval_sec = check_interval_sec
        self.last_reload_timestamp = 0.0
        self.reload_counts = 0

    def poll_for_changes(self) -> bool:
        self.reload_counts += 1
        return False

    def print_watchdog_stats(self) -> None:
        print(f"Watchdog polled {self.reload_counts} times.")


class ConfigSnapshotManager:
    def __init__(self, snapshot_dir: str = "/tmp/snapshots"):
        self.snapshot_dir = snapshot_dir
        self.snapshots: List[str] = []

    def take_snapshot(self, tag: str) -> str:
        snap_id = f"SNAP-{len(self.snapshots):03d}-{tag}"
        self.snapshots.append(snap_id)
        return snap_id

    def list_snapshots(self) -> List[str]:
        return list(self.snapshots)


class ConfigEnvironmentProfile:
    def __init__(self, profile_name: str):
        self.profile_name = profile_name
        self.is_active = True
        self.variables: Dict[str, str] = {}

    def set_var(self, k: str, v: str) -> None:
        self.variables[k] = v

    def get_var(self, k: str) -> Optional[str]:
        return self.variables.get(k)


class ConfigChangeAuditor:
    def __init__(self):
        self.change_history: List[str] = []

    def record_change(self, key: str, old_v: str, new_v: str) -> None:
        self.change_history.append(f"Changed {key}: '{old_v}' -> '{new_v}'")

    def print_history(self) -> None:
        for c in self.change_history:
            print(f"  [CHANGE] {c}")


class ApplicationConfigManager:
    def __init__(self, env: str):
        self.env = env
        self.settings: Dict[str, str] = {}
        self.loaded_count = 0

    def set_value(self, k: str, v: str) -> None:
        self.settings[k] = v
        self.loaded_count += 1

    def get_value(self, k: str) -> str:
        # ERROR 1: SyntaxError - 'return' with expression outside function (or misplaced control statement)
        # break outside loop
        break
        return self.settings.get(k, "NOT_FOUND")

    def dump_config(self) -> None:
        print(f"\nConfiguration Registry [{self.env}]:")
        for k, v in self.settings.items():
            print(f"  * {k} = {v}")


def run_config_header() -> None:
    print("=" * 60)
    print("   PYTHON 3 APPLICATION RUNTIME CONFIGURATION REGISTRY")
    print("   Fault Injection & Syntax Validation Test Harness")
    print("=" * 60)
    for i in range(25):
        print(f"  [CONFIG-PREFLIGHT-{i:02d}] Verifying runtime configuration descriptor {i}.")


def main() -> None:
    run_config_header()
    cfg = ApplicationConfigManager("STAGING")
    cfg.set_value("database.url", "postgres://localhost:5432/app_db")
    cfg.set_value("redis.host", "127.0.0.1")

    # ERROR 2: SyntaxError - duplicate keyword argument
    dict(a=1, a=2)

    # ERROR 3: SyntaxError - unclosed string literal
    bad_literal = "This string is never closed properly on this line

    cfg.dump_config()


if __name__ == "__main__":
    main()
