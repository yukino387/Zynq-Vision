"""Build a PL-contract-compliant placeholder model for pipeline testing.

The fixed graph, tensor layout, quantization fields and package format are the
real ones from camera/training/pl_model.py. Only the weights are synthetic.
"""
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
import torch

ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera" / "training"))

from pl_model import (  # noqa: E402
    COMMANDS,
    FixedGraph,
    METADATA_WORDS,
    OUTPUT_SCALES,
    WEIGHT_BYTES,
    commands_for,
    export_int8,
)

VERSION = "PL-TEST-GENERIC-20261018"
CLASSES = [f"object_{i}" for i in range(6)]
OUT = Path(__file__).parent / "out"


def build():
    torch.manual_seed(7020)
    model = FixedGraph(1).eval()
    maximum = [0.0]

    def observe(index, value):
        # Mirror train.py: the two heads keep their fixed output scales.
        if index not in (26, 32):
            maximum[0] = max(maximum[0], value.abs().max().item())

    with torch.inference_mode():
        for seed in range(4):
            generator = torch.Generator().manual_seed(seed)
            x = torch.randint(0, 128, (1, 1, 224, 224), generator=generator)
            model(x.float() / 127, observe)
    hidden_scale = max(maximum[0] / 127, 1e-6)
    weights, metadata, manifest = export_int8(model, hidden_scale, VERSION, OUT)
    manifest["classes"] = CLASSES
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return weights, metadata, manifest, hidden_scale


def validate(package, version):
    """Replicate apps/server/src/models/zynq-profile.ts checks offline."""
    assert len(package) == 6416360, len(package)
    assert struct.unpack_from("<I", package, 0)[0] == 0x314E4E43
    assert struct.unpack_from("<I", package, 4)[0] == 1
    assert struct.unpack_from("<I", package, 8)[0] == WEIGHT_BYTES
    assert struct.unpack_from("<I", package, 12)[0] == METADATA_WORDS * 4
    assert struct.unpack_from("<I", package, 16)[0] == 0
    assert struct.unpack_from("<I", package, 20)[0] == 0
    assert struct.unpack_from("<I", package, 124)[0] == 0
    assert zlib.crc32(package[:120]) & 0xFFFFFFFF == struct.unpack_from("<I", package, 120)[0]
    assert package[24:88] == version.encode("ascii").ljust(64, b"\0")
    payload = package[128:]
    assert hashlib.sha256(payload).digest() == package[88:120]
    words = np.frombuffer(payload[WEIGHT_BYTES:], dtype="<i4")
    assert np.array_equal(words[:330].reshape(33, 10), commands_for(1))
    for _, _, _, offset, _, co, _, _, kernel, _ in commands_for(1):
        if kernel in (1, 3):
            shifts = words[offset + 2 * co:offset + 3 * co]
            negative = words[offset + 4 * co:offset + 5 * co]
            assert shifts.min() >= 1 and shifts.max() <= 62
            assert negative.min() >= 1 and negative.max() <= 62
        elif kernel == 5:
            assert words[offset] > 0 and 1 <= words[offset + 1] <= 62
    return hashlib.sha256(package).hexdigest()


if __name__ == "__main__":
    weights, metadata, manifest, hidden_scale = build()
    package = (OUT / "model.bin").read_bytes()
    digest = validate(package, VERSION)
    report = {
        "version": VERSION,
        "classes": CLASSES,
        "hiddenScale": hidden_scale,
        "packageBytes": len(package),
        "packageSha256": digest,
        "weightsBytes": len(weights),
        "metadataBytes": len(metadata),
        "note": "Placeholder weights; structural/pipeline test only, no detection accuracy.",
    }
    (OUT / "validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
