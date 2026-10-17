"""Exact little-endian integer tensor comparison. Python standard library only."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


FORMATS = {"int8": ("b", 1), "uint8": ("B", 1), "int16": ("h", 2)}


def read_tensor(path, dtype, count):
    raw = Path(path).read_bytes()
    code, width = FORMATS[dtype]
    if len(raw) != count * width:
        raise ValueError(f"{path}: expected {count * width} bytes, found {len(raw)}")
    values = [item[0] for item in struct.iter_unpack("<" + code, raw)]
    return raw, values


def compare(reference, actual, dtype, count):
    if count <= 0:
        raise ValueError("count must be positive")
    ref_raw, ref = read_tensor(reference, dtype, count)
    actual_raw, observed = read_tensor(actual, dtype, count)
    mismatch_count = 0
    first = None
    max_error = 0
    for index, (expected, value) in enumerate(zip(ref, observed)):
        if expected != value:
            mismatch_count += 1
            if first is None:
                first = {"index": index, "reference": expected, "actual": value}
            max_error = max(max_error, abs(expected - value))
    return {
        "passed": mismatch_count == 0,
        "dtype": dtype,
        "endianness": "little",
        "count": count,
        "reference": {"path": str(reference), "min": min(ref), "max": max(ref),
                      "sha256": hashlib.sha256(ref_raw).hexdigest()},
        "actual": {"path": str(actual), "min": min(observed), "max": max(observed),
                   "sha256": hashlib.sha256(actual_raw).hexdigest()},
        "mismatch_count": mismatch_count,
        "first_mismatch": first,
        "max_absolute_error": max_error,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--dtype", choices=FORMATS, required=True)
    parser.add_argument("--count", type=int, required=True)
    args = parser.parse_args()
    try:
        result = compare(args.reference, args.actual, args.dtype, args.count)
    except (OSError, ValueError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
