"""Read-only, bounded FPGA engineering summaries. Python standard library."""
import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"


def provenance(path):
    path = Path(path).resolve()
    result = {"path": str(path), "exists": path.is_file()}
    if result["exists"]:
        stat = path.stat()
        result.update(bytes=stat.st_size,
                      modified_utc=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat())
    return result


def read_report(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def log_tail(path):
    source = provenance(path)
    with Path(path).open("rb") as handle:
        offset = max(0, source["bytes"] - 65536)
        handle.seek(offset)
        lines = handle.read().decode("utf-8", errors="replace").splitlines()
        if offset and lines:
            lines = lines[1:]
    errors = [line[:240] for line in lines if re.search(r"^\s*(?:ERROR(?::|\s+\[)|FATAL(?::|\s+\[)|TEST ERROR\b|Verification failed\b)", line, re.I)]
    warnings = [line[:240] for line in lines if re.search(r"^\s*WARNING:", line)]
    events = [line[:240] for line in lines if re.search(r"^Phase |PASS:|\bERROR\b|Congestion|constraints are|bitstream|write_bitstream|Exiting Vivado", line, re.I)]
    return {"source": source, "scope": "last_64KiB_only", "tail_error_lines": len(errors),
            "last_errors": errors[-3:], "last_warnings": warnings[-2:], "events": events[-4:],
            "last_line": next((line[:240] for line in reversed(lines) if line.strip()), ""),
            "process_state": "unknown"}


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            encoding="utf-8", errors="replace", timeout=15)
    if result.returncode:
        raise ValueError(result.stderr.strip()[:300])
    return result.stdout


def status(args):
    root = Path(args.root).resolve()
    output = {"root": str(root), "head": git(root, "rev-parse", "--short", "HEAD").strip()}
    raw = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=normal").split("\0")
    entries = []
    index = 0
    while index < len(raw):
        entry = raw[index]
        index += 1
        if not entry:
            continue
        item = {"status": entry[:2], "path": entry[3:]}
        if "R" in entry[:2] or "C" in entry[:2]:
            item["from"] = raw[index]
            index += 1
        entries.append(item)
    output.update(changed_count=len(entries), changes=entries[:args.limit],
                  omitted_changes=max(0, len(entries) - args.limit))
    if args.log:
        output["log"] = log_tail(args.log)
    if args.artifact:
        output["artifact"] = provenance(args.artifact)
        if args.sha256 and output["artifact"]["exists"]:
            digest = hashlib.sha256()
            with Path(args.artifact).open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            output["artifact"]["sha256"] = digest.hexdigest()
    return output


def timing(path):
    text = read_report(path)
    section = text.split("| Design Timing Summary", 1)[-1] if "| Design Timing Summary" in text else ""
    values = None
    for line in section.splitlines():
        fields = line.split()
        if len(fields) == 12 and all(re.fullmatch(NUMBER, value) for value in fields):
            values = list(map(float, fields))
            break
    metrics = None if values is None else dict(zip(
        ("wns_ns", "tns_ns", "setup_failing", "setup_total", "whs_ns", "ths_ns",
         "hold_failing", "hold_total", "wpws_ns", "tpws_ns", "pulse_failing", "pulse_total"), values))
    checks = {name: int(count) for name, count in re.findall(r"checking (\w+) \((\d+)\)", text)}
    state = re.search(r"Design State\s*:\s*(.+)", text)
    date = re.search(r"\| Date\s*:\s*(.+)", text)
    passed = None if metrics is None else all(metrics[key] >= 0 for key in ("wns_ns", "whs_ns", "wpws_ns")) and all(metrics[key] == 0 for key in ("tns_ns", "ths_ns", "tpws_ns", "setup_failing", "hold_failing", "pulse_failing"))
    return {"source": provenance(path), "report_date": date.group(1).strip() if date else None,
            "design_state": state.group(1).strip() if state else None,
            "metrics": metrics, "reported_checks": checks,
            "numeric_timing_pass": passed, "complete_signoff": False}


def utilization(path):
    text = read_report(path)
    resources = {}
    for label in ("Slice LUTs", "Slice Registers", "Block RAM Tile", "DSPs"):
        match = re.search(r"^\|\s*" + re.escape(label) + r"\s*\|(.+)$", text, re.M)
        if match:
            fields = [field.strip() for field in match.group(1).split("|") if field.strip()]
            if len(fields) >= 5 and all(re.fullmatch(NUMBER, value) for value in fields[:5]):
                resources[label] = {"used": float(fields[0]), "available": float(fields[3]),
                                    "percent": float(fields[4])}
    state = re.search(r"Design State\s*:\s*(.+)", text)
    return {"source": provenance(path), "design_state": state.group(1).strip() if state else None,
            "resources": resources, "missing_labels": [label for label in ("Slice LUTs", "Slice Registers", "Block RAM Tile", "DSPs") if label not in resources],
            "bram_unit": "36K_tile"}


def bus_skew(path):
    text = read_report(path)
    slacks = [float(match[2]) for match in re.findall(
        r"^\s*(?:Slow|Fast)\s+(" + NUMBER + r")\s+(" + NUMBER + r")\s+(" + NUMBER + r")\s*$", text, re.M)]
    return {"source": provenance(path), "summary_rows": len(slacks),
            "minimum_slack_ns": min(slacks) if slacks else None,
            "summary_pass": all(value >= 0 for value in slacks) if slacks else None}


def hls(path):
    root = ET.parse(path).getroot()
    def get(key):
        return root.findtext(key)
    resources = root.find("AreaEstimates/Resources")
    loops = root.find("PerformanceEstimates/SummaryOfLoopLatency")
    loop_rows = [] if loops is None else [{"name": node.tag, "ii": node.findtext("PipelineII"),
                                           "depth": node.findtext("PipelineDepth")} for node in loops]
    interval = "PerformanceEstimates/SummaryOfOverallLatency/"
    return {"source": provenance(path), "top": get("UserAssignments/TopModelName"),
            "target_clock_ns": get("UserAssignments/TargetClockPeriod"),
            "estimated_clock_ns": get("PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod"),
            "interval_min": get(interval + "Interval-min"), "interval_max": get(interval + "Interval-max"),
            "loops": loop_rows[:4], "omitted_loops": max(0, len(loop_rows) - 4),
            "estimated_resources": {node.tag: node.text for node in resources} if resources is not None else None,
            "bram_unit": "18K_block", "actual_hardware_resources": False}


def build(args):
    output = {}
    for key, fn in (("timing", timing), ("utilization", utilization), ("bus_skew", bus_skew)):
        path = getattr(args, key)
        if path:
            output[key] = fn(path)
    if args.hls:
        output["hls"] = [hls(path) for path in args.hls]
    if not output:
        raise ValueError("provide at least one report")
    output["release_approved"] = False
    return output


def samples(values):
    if not isinstance(values, list) or not values or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("timings must be a nonempty list of positive finite numbers")
    return {"n": len(values), "median_us": statistics.median(values), "min_us": min(values), "max_us": max(values)}


def perf(args):
    data = json.loads(read_report(args.comparison))
    baseline = samples(data["baseline_forward_us"])
    candidate = samples(data["candidate_forward_us"])
    layers = []
    seen = set()
    for row in data["layers"]:
        name = row["layer"]
        if name in seen:
            raise ValueError("duplicate layer name: " + name)
        seen.add(name)
        old, new = row["baseline_us"], row["candidate_us"]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in (old, new)):
            raise ValueError("invalid layer timing: " + name)
        layers.append({"layer": name, "baseline_us": old, "candidate_us": new, "saved_us": old - new})
    old, new = baseline["median_us"], candidate["median_us"]
    return {"source": provenance(args.comparison), "baseline": baseline, "candidate": candidate,
            "saved_us": old - new, "latency_reduction_percent": round((old - new) / old * 100, 3),
            "inference_only_rate_hz": round(1e6 / new, 3), "end_to_end_fps": None,
            "golden_verified_claim": data.get("golden_verified"),
            "candidate_numerically_eligible_claim": data.get("golden_verified") is True,
            "verification_reexecuted": False, "same_conditions_checked": False,
            "layer_count": len(layers),
            "slowest": sorted(layers, key=lambda row: row["candidate_us"], reverse=True)[:args.limit],
            "best_savings": sorted([row for row in layers if row["saved_us"] > 0], key=lambda row: row["saved_us"], reverse=True)[:3],
            "regressions": sorted([row for row in layers if row["saved_us"] < 0], key=lambda row: row["saved_us"])[:3]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    state = commands.add_parser("status")
    state.add_argument("--root", required=True)
    state.add_argument("--log")
    state.add_argument("--artifact")
    state.add_argument("--sha256", action="store_true")
    state.add_argument("--limit", type=int, choices=range(1, 21), default=12)
    reports = commands.add_parser("build")
    for flag in ("timing", "utilization", "bus-skew"):
        reports.add_argument("--" + flag)
    reports.add_argument("--hls", action="append")
    performance = commands.add_parser("perf")
    performance.add_argument("--comparison", required=True)
    performance.add_argument("--limit", type=int, choices=range(1, 21), default=5)
    args = parser.parse_args()
    try:
        result = {"status": status, "build": build, "perf": perf}[args.command](args)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": str(error)[:400]}, ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
