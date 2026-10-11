from pathlib import Path
import numpy as np
from PIL import Image

here = Path(__file__).resolve().parent
pixels = np.fromfile(here / "frame.bin", dtype="<u2").reshape(416, 416)
red, green, blue = pixels >> 11, (pixels >> 5) & 63, pixels & 31
rgb = np.stack(((red << 3) | (red >> 2), (green << 2) | (green >> 4),
                (blue << 3) | (blue >> 2)), axis=-1).astype(np.uint8)
expected = ((rgb.astype(np.uint32) * 512 + 127) // 255).transpose(2, 0, 1).astype("<i2")
actual = np.fromfile(here / "input.bin", dtype="<i2").reshape(3, 416, 416)
if not np.array_equal(actual, expected):
    raise AssertionError("RGB565 -> RGB CHW quantization mismatch")
Image.fromarray(rgb).save(here / "frame.png")
print(f"PASS: all {actual.size} input values match PC conversion; min={actual.min()}, max={actual.max()}")
