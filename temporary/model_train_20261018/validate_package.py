"""Mirror apps/server/src/models/zynq-profile.ts checks for a trained package."""
import hashlib, json, struct, sys, zlib
from pathlib import Path
import numpy as np

run = Path(sys.argv[1])
pkg = (run / "model.bin").read_bytes()
manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
graph = json.loads((Path(r"C:/00_workplace/fpga/cnn_accelerator/camera/training/graph.json")).read_text())
commands = graph["commands"]
WEIGHT_BYTES, METADATA_BYTES = 6350208, 66024
assert len(pkg) == 128 + WEIGHT_BYTES + METADATA_BYTES, len(pkg)
magic, fmt, wb, mb, gen, committed, version, sha = struct.unpack("<6I64s32s", pkg[:120])
version = version.split(b"\0")[0].decode("ascii")
assert magic == 0x314E4E43 and fmt == 1 and wb == WEIGHT_BYTES and mb == METADATA_BYTES
assert gen == 0 and committed == 0
assert struct.unpack("<I", pkg[120:124])[0] == zlib.crc32(pkg[:120])
assert hashlib.sha256(pkg[128:]).digest() == sha
assert hashlib.sha256(pkg).hexdigest() == manifest["weights"]["sha256"]
assert manifest["weights"]["size"] == len(pkg)
metadata = np.frombuffer(pkg[128 + WEIGHT_BYTES:], dtype="<i4")
channels = manifest["input"]["channels"]
for i, command in enumerate(commands):
    for j, value in enumerate(command):
        expect = channels if (i == 0 and j == 4) else value
        assert metadata[i * 10 + j] == expect, (i, j)
for command in commands:
    offset, co, kernel = command[3], command[5], command[8]
    if kernel in (1, 3):
        for c in range(co):
            for scale in (1, 3):
                assert metadata[offset + scale * co + c] > 0
                assert 1 <= metadata[offset + (scale + 1) * co + c] <= 62
    elif kernel == 5:
        assert metadata[offset] > 0 and 1 <= metadata[offset + 1] <= 62
assert len(manifest["classes"]) == 6 and len(set(manifest["classes"])) == 6
print(json.dumps({"version": version, "bytes": len(pkg), "channels": channels,
                  "classes": manifest["classes"], "sha256": manifest["weights"]["sha256"]}, ensure_ascii=False, indent=1))
