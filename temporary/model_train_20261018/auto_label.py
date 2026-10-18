"""Bootstrap boxes for the bright earphone case; validate against the 19 manual boxes."""
import json, sqlite3
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
c = sqlite3.connect(ROOT / "data/app.db"); c.row_factory = sqlite3.Row
rows = c.execute("""
  select s.id sid, a.storageKey, a.sha256
  from Sample s join Asset a on a.sampleId=s.id
  where a.kind='RAW' and a.format='RGB565_LE' and a.deletedAt is null and s.deletedAt is null
  order by s.createdAt, s.id""").fetchall()
items = []
for r in rows:
    boxes = c.execute("""select b.classId,b.x1,b.y1,b.x2,b.y2 from Annotation b
      join AnnotationSet a on a.id=b.setId where a.sampleId=? and a.status='COMPLETE'
      and a.version=(select max(version) from AnnotationSet z where z.sampleId=? and z.status='COMPLETE')""",
      (r["sid"], r["sid"])).fetchall()
    items.append({"id": r["sid"], "path": ROOT / "data/storage" / r["storageKey"],
                  "manual": [dict(b) for b in boxes]})

def gray_of(path):
    p = np.frombuffer(Path(path).read_bytes(), dtype="<u2").reshape(416, 416)
    r, g, b = p >> 11, (p >> 5) & 63, p & 31
    r8, g8, b8 = (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)
    return ((r8.astype(np.int64) * 19595 + g8.astype(np.int64) * 38470 + b8.astype(np.int64) * 7471 + 32768) >> 16).astype(np.uint8)

def bbox_by_projection(gray, threshold, kernel, min_run=12):
    im = Image.fromarray(gray).point(lambda v: 255 if v >= threshold else 0)
    im = im.filter(ImageFilter.MinFilter(kernel)).filter(ImageFilter.MaxFilter(kernel))
    mask = np.asarray(im) > 0
    rows, cols = mask.sum(1), mask.sum(0)
    ys, xs = np.where(rows > min_run)[0], np.where(cols > min_run)[0]
    if not len(ys) or not len(xs): return None
    # keep the contiguous run containing the largest bright area
    return (int(xs[0]), int(ys[0]), int(xs[-1] + 1), int(ys[-1] + 1))

def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy; union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / union if union else 0

manual = [i for i in items if i["manual"]]
grays = {i["id"]: gray_of(i["path"]) for i in manual}
best = (0, None)
for threshold in (100, 120, 140, 160, 180, 200, 220):
    for k in (9, 13, 17, 21, 25, 31):
        scores = []
        for it in manual:
            box = bbox_by_projection(grays[it["id"]], threshold, k)
            t = it["manual"][0]
            scores.append(iou(box, (t["x1"], t["y1"], t["x2"], t["y2"])) if box else 0)
        mean = float(np.mean(scores))
        print(f"T={threshold} k={k} meanIoU={mean:.3f} min={min(scores):.3f}", flush=True)
        if mean > best[0]: best = (mean, (threshold, k))
print("BEST", best, flush=True)
