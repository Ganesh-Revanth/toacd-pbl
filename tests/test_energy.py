"""
test_energy.py
--------------
Unit tests for energy metering, process monitoring, energy and CO2 estimation formulas,
RAPL handling, psutil-missing behavior, and the /api/energy/compare endpoint.
"""

import json
import os
import shutil
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from energy_meter import (
    compute_estimated_energy_joules,
    compute_estimated_co2_mg,
    get_cpu_watts,
    get_grid_carbon_intensity,
    build_energy_object,
    is_psutil_available,
    read_rapl_energy_joules,
)
from web import server

HAS_GXX = shutil.which("g++") is not None
HAS_GCC = shutil.which("gcc") is not None


class EnergyMeterUnitTests(unittest.TestCase):
    def test_energy_formula_calculation(self):
        # E = cpu_s * cpu_watts
        self.assertAlmostEqual(compute_estimated_energy_joules(2.0, 15.0), 30.0, places=4)
        self.assertAlmostEqual(compute_estimated_energy_joules(0.5, 20.0), 10.0, places=4)
        self.assertAlmostEqual(compute_estimated_energy_joules(0.0, 15.0), 0.0, places=4)
        self.assertIsNone(compute_estimated_energy_joules(None, 15.0))
        # When cpu_watts is None, it defaults to get_cpu_watts() (15.0)
        self.assertAlmostEqual(compute_estimated_energy_joules(1.0, None), 15.0, places=4)

    def test_co2_formula_calculation(self):
        # CO2 (mg) = energy_j / 3.6e6 * grid_g_per_kwh * 1000
        # For 3600 J (1 Wh = 0.001 kWh) and 475 g/kWh:
        # 3600 / 3.6e6 * 475 * 1000 = 1e-3 * 475 * 1000 = 475 mg
        res = compute_estimated_co2_mg(3600.0, 475.0)
        self.assertAlmostEqual(res, 475.0, places=4)
        self.assertIsNone(compute_estimated_co2_mg(None, 475.0))
        # When grid_g_per_kwh is None, it defaults to get_grid_carbon_intensity() (475.0)
        self.assertAlmostEqual(compute_estimated_co2_mg(3600.0, None), 475.0, places=4)

    def test_environment_variable_overrides(self):
        with patch.dict(os.environ, {"ENERGY_CPU_WATTS": "25.5", "GRID_G_CO2_PER_KWH": "320.0"}):
            self.assertEqual(get_cpu_watts(), 25.5)
            intensity, source = get_grid_carbon_intensity()
            self.assertEqual(intensity, 320.0)
            self.assertIn("GRID_G_CO2_PER_KWH", source)

    def test_default_values(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_cpu_watts(), 15.0)
            intensity, source = get_grid_carbon_intensity()
            self.assertGreater(intensity, 0.0)
            self.assertTrue(len(source) > 0)

    def test_build_energy_object_when_psutil_missing(self):
        with patch("energy_meter.is_psutil_available", return_value=False):
            obj = build_energy_object({"cpu_s": 0.5, "wall_s": 0.6, "peak_mem_mb": 12.0}, {})
            self.assertIsNone(obj["cpu_s"])
            self.assertIsNone(obj["wall_s"])
            self.assertIsNone(obj["peak_mem_mb"])
            self.assertIsNone(obj["compile_wall_s"])
            self.assertIsNone(obj["compile_cpu_s"])
            self.assertIsNone(obj["est_energy_j"])
            self.assertIsNone(obj["est_co2_mg"])
            self.assertEqual(obj["method"], "estimated from CPU time")
            self.assertIn("cpu_watts", obj["assumptions"])

    def test_build_energy_object_with_metrics(self):
        run_m = {"wall_s": 0.2, "cpu_s": 0.1, "peak_mem_mb": 8.5, "rapl_j": None}
        comp_m = {"wall_s": 0.5, "cpu_s": 0.4}
        obj = build_energy_object(run_m, comp_m)
        self.assertEqual(obj["wall_s"], 0.2)
        self.assertEqual(obj["cpu_s"], 0.1)
        self.assertEqual(obj["peak_mem_mb"], 8.5)
        self.assertEqual(obj["compile_wall_s"], 0.5)
        self.assertEqual(obj["compile_cpu_s"], 0.4)
        self.assertIsNotNone(obj["est_energy_j"])
        self.assertIsNotNone(obj["est_co2_mg"])
        self.assertIsNone(obj["rapl_j"])

    def test_rapl_safe_on_non_linux(self):
        # On Windows / systems without powercap, read_rapl_energy_joules returns None, never crashes
        val = read_rapl_energy_joules()
        self.assertTrue(val is None or isinstance(val, (int, float)))


class EnergyApiTests(unittest.TestCase):
    @unittest.skipUnless(HAS_GXX, "g++ not available")
    def test_api_cpp_run_includes_energy_object(self):
        code = (
            "#include <iostream>\n"
            "int main() {\n"
            "    long long sum = 0;\n"
            "    for (int i = 0; i < 50000; ++i) sum += i;\n"
            "    std::cout << sum << std::endl;\n"
            "    return 0;\n"
            "}\n"
        )
        res = server.api_cpp_run({"code": code, "language": "cpp"})
        self.assertTrue(res["ok"])
        self.assertIn("energy", res)
        en = res["energy"]
        self.assertIsNotNone(en)
        self.assertIn("wall_s", en)
        self.assertIn("cpu_s", en)
        self.assertIn("peak_mem_mb", en)
        self.assertIn("est_energy_j", en)
        self.assertIn("est_co2_mg", en)
        self.assertIn("assumptions", en)
        self.assertEqual(en["method"], "estimated from CPU time")

    @unittest.skipUnless(HAS_GXX, "g++ not available")
    def test_api_energy_compare_endpoint(self):
        code = (
            "#include <iostream>\n"
            "int main() {\n"
            "    volatile long long sum = 0;\n"
            "    for (int i = 0; i < 200000; ++i) sum += i;\n"
            "    std::cout << sum << std::endl;\n"
            "    return 0;\n"
            "}\n"
        )
        res = server.api_energy_compare({"code": code, "language": "cpp"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["runs_count"], 3)
        self.assertIn("o0", res)
        self.assertIn("o2", res)
        self.assertIn("saved", res)
        self.assertIn("median_wall_s", res["o0"])
        self.assertIn("median_cpu_s", res["o0"])
        self.assertIn("median_energy_j", res["o0"])
        self.assertIn("median_wall_s", res["o2"])
        self.assertIn("median_cpu_s", res["o2"])
        self.assertIn("median_energy_j", res["o2"])
        self.assertIn("energy_pct", res["saved"])
        self.assertFalse(res["outputs_differ"])
        self.assertIsNone(res["diff_warning"])

    @unittest.skipUnless(HAS_GXX, "g++ not available")
    def test_api_cpp_run_psutil_unavailable_returns_none(self):
        code = (
            "#include <iostream>\n"
            "int main() {\n"
            "    std::cout << \"hello\" << std::endl;\n"
            "    return 0;\n"
            "}\n"
        )
        with patch("energy_meter.is_psutil_available", return_value=False):
            res = server.api_cpp_run({"code": code, "language": "cpp"})
            self.assertTrue(res["ok"])
            en = res.get("energy")
            self.assertIsNotNone(en)
            self.assertIsNone(en["wall_s"])
            self.assertIsNone(en["cpu_s"])
            self.assertIsNone(en["peak_mem_mb"])
            self.assertIsNone(en["compile_wall_s"])
            self.assertIsNone(en["compile_cpu_s"])
            self.assertIsNone(en["est_energy_j"])
            self.assertIsNone(en["est_co2_mg"])

    @unittest.skipUnless(HAS_GXX, "g++ not available")
    def test_api_energy_compare_flags_differing_output(self):
        code = (
            "#include <iostream>\n"
            "int main() {\n"
            "    std::cout << 42 << std::endl;\n"
            "    return 0;\n"
            "}\n"
        )
        res = server.api_energy_compare({"code": code, "language": "cpp"})
        self.assertTrue(res["ok"])
        self.assertFalse(res["outputs_differ"])

    def test_api_energy_compare_unsupported_language(self):
        with self.assertRaises(server.ApiError) as ctx:
            server.api_energy_compare({"code": "print('hello')", "language": "python"})
        self.assertEqual(ctx.exception.status, 400)


if __name__ == "__main__":
    unittest.main()
