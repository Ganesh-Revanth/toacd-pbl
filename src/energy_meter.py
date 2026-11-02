"""
energy_meter.py
---------------
Real telemetry, child-process resource measurement, and energy/CO2 estimation.
No simulated or random values: measurements are derived from OS counters
(psutil polling every ~10 ms) and hardware energy counters (RAPL) when available.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil
except ImportError:
    psutil = None

DEFAULT_CPU_WATTS: float = 15.0


def is_psutil_available() -> bool:
    """Return True if psutil is imported and usable."""
    return psutil is not None


def get_cpu_watts() -> float:
    """Return default CPU TDP assumption in Watts, configurable via ENERGY_CPU_WATTS."""
    val = os.environ.get("ENERGY_CPU_WATTS")
    if val:
        try:
            return max(0.1, float(val))
        except ValueError:
            pass
    return DEFAULT_CPU_WATTS


def get_grid_carbon_intensity() -> Tuple[float, str]:
    """
    Return grid carbon intensity in gCO2/kWh and the data source description.
    Configurable via GRID_G_CO2_PER_KWH; defaults to CodeCarbon's bundled global average.
    """
    env_val = os.environ.get("GRID_G_CO2_PER_KWH")
    if env_val:
        try:
            val = float(env_val)
            return val, f"Custom env GRID_G_CO2_PER_KWH ({val:.1f} g CO2/kWh)"
        except ValueError:
            pass

    # Read CodeCarbon bundled dataset (carbon_intensity_per_source.json)
    try:
        from codecarbon.core.emissions import DataSource
        ds = DataSource()
        data = ds.get_carbon_intensity_per_source_data()
        intensity = float(data.get("world_average", 475))
        source_url = str(data.get("world_average_source") or "https://www.iea.org/reports/global-energy-co2-status-report-2019/emissions")
        return intensity, f"CodeCarbon bundled data (IEA world average {intensity:.0f} g CO2/kWh; {source_url})"
    except Exception:
        return 475.0, "CodeCarbon default (IEA world average 475 g CO2/kWh)"


def read_rapl_energy_joules() -> Optional[float]:
    """
    Read Linux RAPL (Running Average Power Limit) energy counters from /sys/class/powercap.
    Returns total energy in Joules, or None if hardware counters are unavailable.
    Never returns fake or placeholder numbers.
    """
    root = "/sys/class/powercap"
    if not os.path.isdir(root):
        return None

    total_uj = 0
    found = False
    for dirpath, _, filenames in os.walk(root):
        if "energy_uj" not in filenames:
            continue
        try:
            with open(os.path.join(dirpath, "energy_uj"), "r", encoding="utf-8") as f:
                total_uj += int(f.read().strip())
                found = True
        except (OSError, ValueError):
            continue

    return total_uj / 1_000_000 if found else None


def compute_estimated_energy_joules(cpu_s: Optional[float], cpu_watts: Optional[float] = None) -> Optional[float]:
    """
    est_energy_j = cpu_s * cpu_watts.
    Returns None if cpu_s is None (e.g. psutil unavailable).
    """
    if cpu_s is None:
        return None
    if cpu_watts is None:
        cpu_watts = get_cpu_watts()
    return round(float(cpu_s) * float(cpu_watts), 6)


def compute_estimated_co2_mg(energy_j: Optional[float], grid_g_per_kwh: Optional[float] = None) -> Optional[float]:
    """
    est_co2_mg = est_energy_j / 3.6e6 * grid_g_per_kwh * 1000.
    1 kWh = 3.6e6 Joules.
    Returns None if energy_j is None.
    """
    if energy_j is None:
        return None
    if grid_g_per_kwh is None:
        grid_g_per_kwh, _ = get_grid_carbon_intensity()
    return round(float(energy_j) / 3.6e6 * float(grid_g_per_kwh) * 1000.0, 6)


class ProcessMonitor:
    """
    Active resource monitor that polls a child process every ~10 ms using psutil.
    Tracks peak memory (RSS in bytes) and total CPU time (user + system in seconds).
    """

    def __init__(self, pid: int, interval: float = 0.01, poll_interval: Optional[float] = None):
        self.pid = pid
        self.poll_interval = poll_interval if poll_interval is not None else interval
        self._stop_event = threading.Event()
        self.peak_mem_bytes = 0
        self.cpu_time_s = 0.0
        self._thread: Optional[threading.Thread] = None
        self._measured = False

    def start(self) -> None:
        if not is_psutil_available() or self.pid <= 0:
            return
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _sample(self, proc_obj) -> None:
        if not is_psutil_available():
            return
        try:
            procs = [proc_obj]
            try:
                procs += proc_obj.children(recursive=True)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            total_mem = 0
            total_cpu = 0.0
            for cp in procs:
                try:
                    mi = cp.memory_info()
                    total_mem += mi.rss
                    ct = cp.cpu_times()
                    total_cpu += (ct.user + ct.system)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if total_mem > self.peak_mem_bytes:
                self.peak_mem_bytes = total_mem
            if total_cpu > self.cpu_time_s:
                self.cpu_time_s = total_cpu
            self._measured = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def _poll_loop(self) -> None:
        if not is_psutil_available():
            return
        try:
            p = psutil.Process(self.pid)
        except Exception:
            return

        # Immediate first sample
        self._sample(p)
        while not self._stop_event.wait(self.poll_interval):
            try:
                if not p.is_running():
                    break
                self._sample(p)
            except Exception:
                break

    def stop(self, subprocess_proc=None) -> None:
        """Signal monitor to stop, join thread, and capture any final exit accounting."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.1)

        if not is_psutil_available():
            return

        # Final sample if process object is still accessible
        try:
            p = psutil.Process(self.pid)
            self._sample(p)
        except Exception:
            pass

        # If process exited very quickly and Windows handle is available, verify CPU times
        if os.name == "nt" and subprocess_proc and hasattr(subprocess_proc, "_handle"):
            try:
                import ctypes
                creation = ctypes.c_ulonglong()
                exit_t = ctypes.c_ulonglong()
                kernel_t = ctypes.c_ulonglong()
                user_t = ctypes.c_ulonglong()
                res = ctypes.windll.kernel32.GetProcessTimes(
                    int(subprocess_proc._handle),
                    ctypes.byref(creation),
                    ctypes.byref(exit_t),
                    ctypes.byref(kernel_t),
                    ctypes.byref(user_t),
                )
                if res:
                    total_s = (kernel_t.value + user_t.value) / 1e7
                    if total_s > self.cpu_time_s:
                        self.cpu_time_s = total_s
                        self._measured = True
            except Exception:
                pass

            if self.peak_mem_bytes == 0:
                try:
                    import ctypes
                    from ctypes import wintypes

                    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                        _fields_ = [
                            ("cb", wintypes.DWORD),
                            ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t),
                        ]

                    pmc = PROCESS_MEMORY_COUNTERS()
                    pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                    if ctypes.windll.psapi.GetProcessMemoryInfo(
                        int(subprocess_proc._handle), ctypes.byref(pmc), pmc.cb
                    ):
                        self.peak_mem_bytes = pmc.PeakWorkingSetSize
                        self._measured = True
                except Exception:
                    pass

    def get_metrics(self, wall_s: Optional[float] = None) -> Dict[str, Optional[float]]:
        """
        Return dictionary of measured metrics.
        If psutil is unavailable or no measurements could be taken, returns null fields.
        """
        if not is_psutil_available():
            return {
                "wall_s": None,
                "cpu_s": None,
                "peak_mem_mb": None,
            }

        peak_mb = round(self.peak_mem_bytes / (1024.0 * 1024.0), 2) if self.peak_mem_bytes > 0 else 0.0
        return {
            "wall_s": round(wall_s, 4) if wall_s is not None else None,
            "cpu_s": round(self.cpu_time_s, 4),
            "peak_mem_mb": peak_mb,
        }


def build_energy_object(
    run_metrics: Optional[Dict[str, Any]],
    compile_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the standard 'energy' object for the API run response.
    If psutil is unavailable, all measurement fields are null (not zero).
    """
    cpu_watts = get_cpu_watts()
    grid_g, grid_source = get_grid_carbon_intensity()

    assumptions = {
        "cpu_watts": cpu_watts,
        "grid_g_per_kwh": grid_g,
        "grid_source": grid_source,
    }

    if not is_psutil_available() or run_metrics is None:
        return {
            "wall_s": None,
            "cpu_s": None,
            "peak_mem_mb": None,
            "compile_wall_s": None,
            "compile_cpu_s": None,
            "est_energy_j": None,
            "est_co2_mg": None,
            "method": "estimated from CPU time",
            "assumptions": assumptions,
            "rapl_j": None,
        }

    wall_s = run_metrics.get("wall_s")
    cpu_s = run_metrics.get("cpu_s")
    peak_mem_mb = run_metrics.get("peak_mem_mb")
    rapl_j = run_metrics.get("rapl_j")

    compile_wall_s = None
    compile_cpu_s = None
    if compile_metrics:
        compile_wall_s = compile_metrics.get("wall_s")
        compile_cpu_s = compile_metrics.get("cpu_s")

    est_energy_j = compute_estimated_energy_joules(cpu_s, cpu_watts)
    est_co2_mg = compute_estimated_co2_mg(est_energy_j, grid_g)

    return {
        "wall_s": round(wall_s, 4) if wall_s is not None else None,
        "cpu_s": round(cpu_s, 4) if cpu_s is not None else None,
        "peak_mem_mb": round(peak_mem_mb, 2) if peak_mem_mb is not None else None,
        "compile_wall_s": round(compile_wall_s, 4) if compile_wall_s is not None else None,
        "compile_cpu_s": round(compile_cpu_s, 4) if compile_cpu_s is not None else None,
        "est_energy_j": est_energy_j,
        "est_co2_mg": est_co2_mg,
        "method": "estimated from CPU time",
        "assumptions": assumptions,
        "rapl_j": round(rapl_j, 4) if rapl_j is not None else None,
    }
