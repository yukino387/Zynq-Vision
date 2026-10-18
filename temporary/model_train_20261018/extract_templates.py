"""Extract carton templates (with/without straw) and a wooden-table background plate."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
OUT = Path(r"C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018")
FILES = {
    "with": Path(r"C:\Users\YUKINO\Downloads\IMG20261018111352.jpg"),
    "without": Path(r"C:\Users\YUKINO\Downloads\IMG20261018111348.jpg"),
    "table": Path(r"C:\Users\YUKINO\Downloads\IMG20261018111406.jpg"),
}

def carton_bbox(path):
    im = Image.open(path).convert("RGB")
    small = im.resize((384, 512), Image.BILINEAR)
    a = np.asarray(small).astype(np.float32)
    mx, mn = a.max(2), a.min(2)
    v = mx; s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    mask = (v > 95) & (s < 0.45)
    cols = mask.sum(0); rows = mask.sum(1)
    def run(sums, th):
        idx = np.where(sums > th)[0]
        if not len(idx): return 0, len(sums) - 1
        breaks = np.where(np.diff(idx) > 1)[0]
        segs = np.split(idx, breaks + 1)
        seg = max(segs, key=len)
        return int(seg[0]), int(seg[-1])
    x0, x1 = run(cols, 0.06 * mask.shape[0]); y0, y1 = run(rows, 0.06 * mask.shape[1])
    sx, sy = im.width / 384, im.height / 512
    x0, x1, y0, y1 = x0 * sx, (x1 + 1) * sx, y0 * sy, (y1 + 1) * sy
    m = 0.04 * max(x1 - x0, y1 - y0)
    return im, (max(0, x0 - m), max(0, y0 - m), min(im.width, x1 + m), min(im.height, y1 + m))

for name, path in FILES.items():
    if name == "table":
        im = Image.open(path).convert("RGB")
        # right-side clean table patch (carton is centered-left in the top-row photos)
        patch = im.crop((int(im.width * 0.68), int(im.height * 0.05), int(im.width * 0.98), int(im.height * 0.55)))
        patch.save(OUT / "table_bg.png"); print("table_bg", patch.size)
        continue
    im, box = carton_bbox(path)
    patch = im.crop(tuple(int(v) for v in box))
    patch.save(OUT / f"template_{name}.png")
    print(name, "image", im.size, "box", tuple(round(v) for v in box), "patch", patch.size)
    prev = im.copy(); d = ImageDraw.Draw(prev); d.rectangle(box, outline=(0,255,0), width=8); prev.thumbnail((600,800)); prev.save(OUT / f"bbox_{name}.jpg", quality=88)
