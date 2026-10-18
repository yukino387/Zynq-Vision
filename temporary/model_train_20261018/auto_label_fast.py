"""Fast auto-label tune on 1/4-scale grayscale; validate against the 19 manual boxes."""
import sqlite3
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
c = sqlite3.connect(ROOT / "data/app.db"); c.row_factory = sqlite3.Row
rows = c.execute("""
  select s.id sid, a.storageKey from Sample s join Asset a on a.sampleId=s.id
  where a.kind='RAW' and a.format='RGB565_LE' and a.deletedAt is null and s.deletedAt is null
  order by s.createdAt, s.id""").fetchall()
items = []
for r in rows:
    boxes = c.execute("""select b.x1,b.y1,b.x2,b.y2 from Annotation b join AnnotationSet a on a.id=b.setId
      where a.sampleId=? and a.status='COMPLETE' and a.version=(select max(version) from AnnotationSet z
      where z.sampleId=? and z.status='COMPLETE')""", (r["sid"], r["sid"])).fetchall()
    items.append({"id": r["sid"], "path": ROOT / "data/storage" / r["storageKey"],
                  "manual": [dict(b) for b in boxes]})

def gray_of(path):
    p = np.frombuffer(Path(path).read_bytes(), dtype="<u2").reshape(416, 416)
    r, g, b = p >> 11, (p >> 5) & 63, p & 31
    r8, g8, b8 = (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)
    return ((r8.astype(np.int64) * 19595 + g8.astype(np.int64) * 38470 + b8.astype(np.int64) * 7471 + 32768) >> 16).astype(np.uint8)

def bbox(gray, threshold, kernel):
    im = Image.fromarray(gray).resize((104, 104), Image.BILINEAR)
    im = im.point(lambda v: 255 if v >= threshold else 0)
    im = im.filter(ImageFilter.MinFilter(kernel)).filter(ImageFilter.MaxFilter(kernel))
    m = np.asarray(im) > 0
    rows, cols = m.sum(1), m.sum(0)
    ys, xs = np.where(rows > 3)[0], np.where(cols > 3)[0]
    if not len(ys) or not len(xs): return None
    return (int(xs[0]) * 4, int(ys[0]) * 4, int(xs[-1] + 1) * 4, int(ys[-1] + 1) * 4)

def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy; union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / union if union else 0

manual = [i for i in items if i["manual"]]
grays = {i["id"]: gray_of(i["path"]) for i in manual}
best = (0, None)
for threshold in (100, 120, 140, 160, 180, 200, 220):
    for k in (3, 5, 7, 9, 11):
        scores = []
        for it in manual:
            box = bbox(grays[it["id"]], threshold, k)
            t = it["manual"][0]
            scores.append(iou(box, (t["x1"], t["y1"], t["x2"], t["y2"])) if box else 0)
        mean = float(np.mean(scores))
        print(f"T={threshold} k={k} meanIoU={mean:.3f} min={min(scores):.3f}", flush=True)
        if mean > best[0]: best = (mean, (threshold, k))
print("BEST", best, flush=True)

def bbox_margin(gray, threshold, kernel, margin):
    b = bbox(gray, threshold, kernel)
    return None if b is None else (max(0, b[0]-margin), max(0, b[1]-margin), min(416, b[2]+margin), min(416, b[3]+margin))
for margin in (0, 4, 8, 12, 16, 20, 24, 32):
    scores=[]
    for it in manual:
        b=bbox_margin(grays[it["id"]],140,11,margin); t=it["manual"][0]
        scores.append(iou(b,(t["x1"],t["y1"],t["x2"],t["y2"])) if b else 0)
    print("margin",margin,"mean",round(float(np.mean(scores)),3),"min",round(min(scores),3),flush=True)
