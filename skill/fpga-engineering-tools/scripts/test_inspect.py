"""Isolated parser tests; no FPGA, vendor tools or source-repo mutation."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import importlib.util


def main():
    script = Path(__file__).with_name("inspect.py")
    spec = importlib.util.spec_from_file_location("fpga_inspect", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="fpga_tool_test_") as directory:
        root = Path(directory)
        timing = root / "timing.rpt"
        timing.write_text("| Design State : Routed\n| Design Timing Summary\n"
                          "0.139 0.000 0 179471 0.052 0.000 0 179471 2.870 0.000 0 69250\n"
                          "checking unconstrained_internal_endpoints (0)\n", encoding="utf-8")
        assert module.timing(timing)["numeric_timing_pass"] is True
        timing.write_text("| Design Timing Summary\n-0.1 -2 1 20 0.05 0 0 20 1 0 0 20\n", encoding="utf-8")
        assert module.timing(timing)["numeric_timing_pass"] is False
        timing.write_text("No summary available", encoding="utf-8")
        assert module.timing(timing)["numeric_timing_pass"] is None
        util = root / "util.rpt"
        util.write_text("| DSPs | 213 | 0 | 0 | 220 | 96.82 |\n"
                        "| Block RAM Tile | 120 | 0 | 0 | 140 | 85.71 |\n", encoding="utf-8")
        resources = module.utilization(util)
        assert resources["resources"]["DSPs"]["used"] == 213
        assert resources["missing_labels"] == ["Slice LUTs", "Slice Registers"]
        bus = root / "bus.rpt"
        bus.write_text(" Slow 8.000 1.175 6.825\n Fast 8.000 8.125 -0.125\n", encoding="utf-8")
        assert module.bus_skew(bus)["summary_pass"] is False
        log = root / "run.log"
        log.write_text("ERROR: old error outside scan\n" + "x" * 70000 + "\nPhase 4 Initial Routing\n", encoding="utf-8")
        tail = module.log_tail(log)
        assert tail["tail_error_lines"] == 0 and tail["scope"] == "last_64KiB_only"
        assert tail["process_state"] == "unknown"
        log.write_text('WARNING: normally an ERROR, override enabled\n# error "qualification failed"\n', encoding="utf-8")
        assert module.log_tail(log)["tail_error_lines"] == 0
        with log.open("a", encoding="utf-8") as handle:
            handle.write("ERROR: [Route 35-1] routing failed\n")
        assert module.log_tail(log)["tail_error_lines"] == 1
        hls = root / "hls.xml"
        hls.write_text('<profile><PerformanceEstimates><SummaryOfLoopLatency><tile><PipelineII>1</PipelineII><PipelineDepth>11</PipelineDepth></tile></SummaryOfLoopLatency></PerformanceEstimates></profile>', encoding="utf-8")
        assert module.hls(hls)["loops"][0]["ii"] == "1"
        comparison = root / "comparison.json"
        comparison.write_text(json.dumps({"baseline_forward_us": [90000, 90010, 89990],
                                          "candidate_forward_us": [81000, 81010, 80990],
                                          "golden_verified": False,
                                          "layers": [{"layer": "pool", "baseline_us": 10000, "candidate_us": 2000}]}), encoding="utf-8")
        result = subprocess.run([sys.executable, str(script), "perf", "--comparison", str(comparison)],
                                capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        assert output["saved_us"] == 9000 and output["latency_reduction_percent"] == 10
        assert output["end_to_end_fps"] is None and not output["candidate_numerically_eligible_claim"]
        comparison.write_text('{"baseline_forward_us": []}', encoding="utf-8")
        result = subprocess.run([sys.executable, str(script), "perf", "--comparison", str(comparison)], capture_output=True, text=True)
        assert result.returncode == 2 and "error" in json.loads(result.stdout)
        reference, actual = root / "ref.bin", root / "out.bin"
        reference.write_bytes(bytes([128, 255, 0, 127]))
        actual.write_bytes(reference.read_bytes())
        verifier = script.with_name("verify_tensor.py")
        command = [sys.executable, str(verifier), "--reference", str(reference), "--actual", str(actual), "--dtype", "int8", "--count", "4"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        assert json.loads(result.stdout)["actual"]["min"] == -128
        actual.write_bytes(bytes([128, 255, 1, 127]))
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 1 and json.loads(result.stdout)["first_mismatch"]["index"] == 2
        actual.write_bytes(b"\x00")
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 2
    print("PASS: timing pass/fail/unknown, resource units, negative bus-skew, bounded log, performance claims, malformed input")


if __name__ == "__main__":
    main()
