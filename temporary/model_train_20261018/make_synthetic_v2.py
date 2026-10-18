"""Copy-paste synthetic cartons on the wooden table; same pink carton, class 0 gets a drawn straw."""
import argparse, json, random
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
OUT = ROOT / "temporary/model_train_20261018/synthetic_v2"
OUT.mkdir(exist_ok=True); (OUT / "images").mkdir(exist_ok=True)
PHOTO = Path(r"C:\Users\YUKINO\Downloads\IMG20261018111348.jpg")
BOX = (635, 502, 2313, 2580)  # pink carton, no straw
TABLE = ROOT / "temporary/model_train_20261018/table_bg.png"

def load_carton():
    im = Image.open(PHOTO).convert("RGB")
    return im.crop(BOX).resize((600, 743), Image.LANCZOS)

def draw_straw(patch, rng):
    im = patch.copy(); d = ImageDraw.Draw(im)
    w, h = im.size
    x1, y1 = rng.uniform(0.42, 0.62) * w, rng.uniform(0.02, 0.10) * h
    x2, y2 = rng.uniform(0.18, 0.38) * w, rng.uniform(0.88, 0.99) * h
    width = int(rng.uniform(0.022, 0.038) * w)
    # soft shadow behind the tube
    d.line([(x1 + 4, y1 + 6), (x2 + 4, y2 + 6)], fill=(150, 140, 145), width=width + 4)
    # tube: gray outline + white body + highlight
    d.line([(x1, y1), (x2, y2)], fill=(205, 205, 210), width=width)
    d.line([(x1, y1), (x2, y2)], fill=(248, 248, 250), width=max(2, width - 5))
    d.line([(x1 - width * 0.25, y1), (x2 - width * 0.25, y2)], fill=(255, 255, 255), width=max(1, width // 5))
    # rounded ends
    r = width // 2
    for x, y in ((x1, y1), (x2, y2)):
        d.ellipse([x - r, y - r, x + r, y + r], fill=(245, 245, 248), outline=(200, 200, 205))
    return im

def paste(canvas, patch, angle, scale, pos, box_w, box_h):
    rot = patch.rotate(angle, expand=True, resample=Image.BICUBIC)
    nw, nh = max(1, int(rot.width * scale)), max(1, int(rot.height * scale))
    rot = rot.resize((nw, nh), Image.BICUBIC)
    # alpha = rounded rectangle over the carton, feathered
    alpha = Image.new("L", rot.size, 0); ad = ImageDraw.Draw(alpha)
    r = max(2, int(min(nw, nh) * 0.03))
    ad.rounded_rectangle([2, 2, nw - 3, nh - 3], radius=r, fill=255)
    alpha = alpha.filter(ImageFilter.GaussianBlur(3))
    canvas.paste(rot, (int(pos[0]), int(pos[1])), alpha)
    # transformed carton box (approximate: axis-aligned around the rotated patch)
    x1 = max(0, pos[0]); y1 = max(0, pos[1]); x2 = min(416, pos[0] + nw); y2 = min(416, pos[1] + nh)
    if x2 - x1 < 40 or y2 - y1 < 40: return None
    return [x1, y1, x2, y2]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--count", type=int, default=50); ap.add_argument("--seed", type=int, default=7020)
    args = ap.parse_args(); random.seed(args.seed); rng = np.random.default_rng(args.seed)
    carton = load_carton(); table = Image.open(TABLE).convert("RGB")
    metas = []
    for i in range(args.count):
        tw, th = table.size
        cw = random.randint(320, min(416, tw)); ch = random.randint(320, min(416, th))
        x0 = random.randint(0, tw - cw); y0 = random.randint(0, th - ch)
        bg = table.crop((x0, y0, x0 + cw, y0 + ch)).resize((416, 416), Image.BICUBIC)
        bg = ImageEnhance.Brightness(bg).enhance(random.uniform(0.72, 1.25))
        bg = ImageEnhance.Contrast(bg).enhance(random.uniform(0.75, 1.25))
        if random.random() < 0.5: bg = bg.transpose(Image.FLIP_LEFT_RIGHT)
        if random.random() < 0.3: bg = bg.transpose(Image.FLIP_TOP_BOTTOM)
        boxes = []
        for _ in range(random.randint(1, 3)):
            cls = random.randint(0, 1)
            patch = draw_straw(carton, rng) if cls == 0 else carton
            target = random.uniform(110, 300)
            scale = target / max(patch.width, patch.height)
            angle = random.uniform(-28, 28)
            pos = (random.uniform(-80, 300), random.uniform(-80, 300))
            b = paste(bg, patch, angle, scale, pos, patch.width, patch.height)
            if b: boxes.append({"classId": cls, "x1": b[0], "y1": b[1], "x2": b[2], "y2": b[3]})
        if not boxes: continue
        if random.random() < 0.4: bg = bg.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 1.2)))
        arr = np.asarray(bg).astype(np.int16) + rng.normal(0, random.uniform(0, 4), (416, 416, 3)).astype(np.int16)
        bg = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        p = OUT / "images" / f"syn_{i:05d}.png"; bg.save(p)
        metas.append({"path": str(p), "boxes": boxes})
    (OUT / "meta.json").write_text(json.dumps(metas, ensure_ascii=False, indent=1), encoding="utf-8")
    print("generated", len(metas))

if __name__ == "__main__":
    main()
