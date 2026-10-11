from pathlib import Path
import hashlib

here = Path(__file__).resolve().parent
last = here / "received/frame_000002"
for debug, received, size in (("jtag_out0.bin", "out0.bin", 75 * 13 * 13 * 2),
                             ("jtag_out1.bin", "out1.bin", 75 * 26 * 26 * 2),
                             ("jtag_preview.bin", "preview_rgb565.bin", 416 * 416 * 2)):
    reference = (here / debug).read_bytes()[:size]
    actual = (last / received).read_bytes()
    if len(reference) != size or actual != reference:
        raise AssertionError(f"UDP/DDR mismatch: {received}")
    print(f"PASS: {received}, {size} bytes, sha256={hashlib.sha256(actual).hexdigest()}")
