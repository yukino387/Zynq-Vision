"""Spec 2: 19 manual labels + 12 auto-labeled board frames; 4 manual frames held out."""
import hashlib, json, sqlite3
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
OUT = Path(r"C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018")
VERSION = "INT8-EARPHONE-20261018-B"
CLASSES = ["正面", "反面", "_unused_2", "_unused_3", "_unused_4", "_unused_5"]

c = sqlite3.connect(ROOT / "data/app.db"); c.row_factory = sqlite3.Row
rows = c.execute("""
  select s.id sid, a.storageKey, a.sha256
  from Sample s join Asset a on a.sampleId=s.id
  where s.source='BOARD' and s.taskId='cmvctfolq001aueqgb9y0xzz7' and a.kind='RAW' and a.format='RGB565_LE'
    and a.deletedAt is null and s.deletedAt is null
  order by s.createdAt, s.id""").fetchall()

def gray_of(path):
    p = np.frombuffer(Path(path).read_bytes(), dtype="<u2").reshape(416, 416)
    r, g, b = p >> 11, (p >> 5) & 63, p & 31
    r8, g8, b8 = (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)
    return ((r8.astype(np.int64) * 19595 + g8.astype(np.int64) * 38470 + b8.astype(np.int64) * 7471 + 32768) >> 16).astype(np.uint8)

def auto_box(gray, threshold=140, kernel=11, margin=4):
    im = Image.fromarray(gray).resize((104, 104), Image.BILINEAR)
    im = im.point(lambda v: 255 if v >= threshold else 0)
    im = im.filter(ImageFilter.MinFilter(kernel)).filter(ImageFilter.MaxFilter(kernel))
    m = np.asarray(im) > 0
    ys, xs = np.where(m.sum(1) > 3)[0], np.where(m.sum(0) > 3)[0]
    if not len(ys) or not len(xs): return None
    return [max(0, int(xs[0]) * 4 - margin), max(0, int(ys[0]) * 4 - margin),
            min(416, int(xs[-1] + 1) * 4 + margin), min(416, int(ys[-1] + 1) * 4 + margin)]

items, sheet_cells = [], []
manual_ids = []
for r in rows:
    boxes = c.execute("""select b.classId,b.x1,b.y1,b.x2,b.y2 from Annotation b join AnnotationSet a on a.id=b.setId
      where a.sampleId=? and a.status='COMPLETE' and a.version=(select max(version) from AnnotationSet z
      where z.sampleId=? and z.status='COMPLETE')""", (r["sid"], r["sid"])).fetchall()
    gray = gray_of(ROOT / "data/storage" / r["storageKey"])
    if boxes:
        manual_ids.append(r["sid"])
        use = [{"classId": b["classId"], "x1": b["x1"], "y1": b["y1"], "x2": b["x2"], "y2": b["y2"]} for b in boxes]
        source = "manual"
    else:
        box = auto_box(gray)
        use = [{"classId": 0, "x1": box[0], "y1": box[1], "x2": box[2], "y2": box[3]}] if box else []
        source = "auto"
    items.append({"id": r["sid"], "path": str(ROOT / "data/storage" / r["storageKey"]),
                  "sha256": r["sha256"], "raw": True, "width": 416, "height": 416,
                  "boxes": use, "_source": source, "_gray": gray})

# same 4 held-out manual ids as run1 (every 4th manual item, sorted by createdAt)
val_ids = {manual_ids[i] for i in range(3, len(manual_ids), 4)}
for index, it in enumerate(items):
    it["split"] = "val" if it["id"] in val_ids else "train"
    it.pop("_gray")

# visualize all boxes
cells = []
for it in items:
    p = np.frombuffer(Path(it["path"]).read_bytes(), dtype="<u2").reshape(416, 416)
    r, g, b = p >> 11, (p >> 5) & 63, p & 31
    rgb = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), 2).astype(np.uint8)
    im = Image.fromarray(rgb).resize((208, 208)); d = ImageDraw.Draw(im)
    for box in it["boxes"]:
        d.rectangle([box["x1"] / 2, box["y1"] / 2, box["x2"] / 2, box["y2"] / 2],
                    outline=(0, 255, 0) if it["_source"] == "manual" else (255, 255, 0), width=3)
    d.text((4, 4), ("V " if it["split"] == "val" else "") + it["_source"], fill=(255, 255, 0))
    cells.append(im)
cols = 8; sheet = Image.new("RGB", (cols * 208, ((len(cells) + cols - 1) // cols) * 208), (20, 20, 20))
for i, im in enumerate(cells): sheet.paste(im, ((i % cols) * 208, (i // cols) * 208))
sheet.save(OUT / "spec2_boxes.jpg", quality=90)

checksum = hashlib.sha256(json.dumps(
    [{"sampleId": it["id"], "split": it["split"], "snapshot": {"boxes": it["boxes"]}} for it in items],
    sort_keys=True).encode()).hexdigest()
for it in items: it.pop("_source")
spec = {"options": {"colorMode": "GRAY", "epochs": 300, "batchSize": 4,
                    "learningRate": 0.001, "seed": 7020, "device": "cuda", "amp": True, "workers": 0},
        "items": items, "version": VERSION, "classes": CLASSES, "datasetChecksum": checksum}
(OUT / "spec2.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"board frames {len(items)}, manual {len(manual_ids)}, auto {len(items)-len(manual_ids)}, "
      f"train {sum(i['split']=='train' for i in items)}, val {sum(i['split']=='val' for i in items)}")
print("val ids:", sorted(val_ids))
