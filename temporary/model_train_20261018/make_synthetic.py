"""Copy-paste synthetic milk-carton images from the high-res photos + wooden table plate."""
import argparse, json, random
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
OUT = ROOT / "temporary/model_train_20261018/synthetic"
OUT.mkdir(exist_ok=True)
(OUT / "images").mkdir(exist_ok=True)
# High-res front photos and their carton boxes (left, top, right, bottom) in the 3072x4096 originals.
TEMPLATES = [
    ("with", Path(r"C:\Users\YUKINO\Downloads\IMG20261018111352.jpg"), (513, 614, 2356, 2662), 0),
    ("without", Path(r"C:\Users\YUKINO\Downloads\IMG20261018111348.jpg"), (635, 502, 2313, 2580), 1),
]
TABLE = OUT.parent / "table_bg.png"

def load_template(path, box, margin=50):
    im = Image.open(path).convert("RGB")
    l, t, r, b = box
    l, t = max(0, l - margin), max(0, t - margin)
    r, b = min(im.width, r + margin), min(im.height, b + margin)
    patch = im.crop((l, t, r, b))
    inner = (box[0] - l, box[1] - t, box[2] - l, box[3] - t)  # carton box inside patch
    return patch, inner

def paste_rotated(canvas, patch, inner, angle, scale, pos):
    w, h = patch.size
    # rotate patch and its carton box corners together
    rot = patch.rotate(angle, expand=True, resample=Image.BICUBIC)
    cx, cy = w / 2, h / 2
    rad = -np.deg2rad(angle)  # PIL rotate is counter-clockwise; y down
    ca, sa = np.cos(rad), np.sin(rad)
    def rot_pt(x, y):
        x, y = x - cx, y - cy
        return x * ca - y * sa + rot.width / 2, x * sa + y * ca + rot.height / 2
    corners = [rot_pt(inner[0], inner[1]), rot_pt(inner[2], inner[1]), rot_pt(inner[2], inner[3]), rot_pt(inner[0], inner[3])]
    nw, nh = max(1, int(rot.width * scale)), max(1, int(rot.height * scale))
    rot = rot.resize((nw, nh), Image.BICUBIC)
    pts = [(x * scale + pos[0], y * scale + pos[1]) for x, y in corners]
    x1 = max(0, min(p[0] for p in pts)); x2 = min(416, max(p[0] for p in pts))
    y1 = max(0, min(p[1] for p in pts)); y2 = min(416, max(p[1] for p in pts))
    if x2 - x1 < 40 or y2 - y1 < 40: return None
    # feathered rectangular alpha
    alpha = Image.new("L", patch.size, 255).filter(ImageFilter.GaussianBlur(18))
    arot = alpha.rotate(angle, expand=True, resample=Image.BICUBIC).resize((nw, nh), Image.BILINEAR)
    canvas.paste(rot, (int(pos[0]), int(pos[1])), arot)
    return [x1, y1, x2, y2]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--count", type=int, default=50); ap.add_argument("--seed", type=int, default=7020)
    args = ap.parse_args(); random.seed(args.seed); rng = np.random.default_rng(args.seed)
    templates = [(name, *load_template(path, box), cls) for name, path, box, cls in TEMPLATES]
    table = Image.open(TABLE).convert("RGB")
    metas = []
    for i in range(args.count):
        # random wooden-table background
        tw, th = table.size
        cw = random.randint(320, min(416, tw)); ch = random.randint(320, min(416, th))
        x0 = random.randint(0, tw - cw); y0 = random.randint(0, th - ch)
        bg = table.crop((x0, y0, x0 + cw, y0 + ch)).resize((416, 416), Image.BICUBIC)
        bg = bg.convert("RGB")
        bg = ImageEnhance.Brightness(bg).enhance(random.uniform(0.75, 1.25))
        bg = ImageEnhance.Contrast(bg).enhance(random.uniform(0.75, 1.25))
        if random.random() < 0.5: bg = bg.transpose(Image.FLIP_LEFT_RIGHT)
        if random.random() < 0.3: bg = bg.transpose(Image.FLIP_TOP_BOTTOM)
        boxes = []
        for _ in range(random.randint(1, 3)):
            name, patch, inner, cls = random.choice(templates)
            # target carton size 110..300 px
            target = random.uniform(110, 300)
            scale = target / max(inner[2] - inner[0], inner[3] - inner[1])
            angle = random.uniform(-28, 28)
            pos = (random.uniform(-60, 300), random.uniform(-60, 300))
            b = paste_rotated(bg, patch, inner, angle, scale, pos)
            if b: boxes.append({"classId": cls, "x1": b[0], "y1": b[1], "x2": b[2], "y2": b[3]})
        if not boxes: continue
        # mild sensor-like degradation
        if random.random() < 0.4: bg = bg.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 1.2)))
        arr = np.asarray(bg).astype(np.int16) + rng.normal(0, random.uniform(0, 4), (416, 416, 3)).astype(np.int16)
        bg = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        p = OUT / "images" / f"syn_{i:05d}.png"; bg.save(p)
        metas.append({"path": str(p), "boxes": boxes})
    (OUT / "meta.json").write_text(json.dumps(metas, ensure_ascii=False, indent=1), encoding="utf-8")
    print("generated", len(metas))

if __name__ == "__main__":
    main()
