"""Cluster the 60 milk frames by background (outside the carton box)."""
import json, sqlite3
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
c = sqlite3.connect(ROOT / "data/app.db"); c.row_factory = sqlite3.Row
rows = c.execute("""select i.sampleId,i.snapshot,a.storageKey from DatasetItem i join Asset a on a.sampleId=i.sampleId
 where i.datasetId='cmvd7apcz0163uea43cbxudgt' and a.kind='PREVIEW' and a.deletedAt is null
 order by i.sampleId""").fetchall()
feats, meta = [], []
for r in rows:
    snap = json.loads(r["snapshot"]); b = snap["boxes"][0]; cls = int(b["classId"])
    im = Image.open(ROOT / "data/storage" / r["storageKey"]).convert("RGB").resize((128, 128))
    arr = np.asarray(im).astype(np.float32)
    mask = np.ones((128, 128), bool)
    x1, y1 = int(b["x1"] / 416 * 128) - 6, int(b["y1"] / 416 * 128) - 6
    x2, y2 = int(b["x2"] / 416 * 128) + 6, int(b["y2"] / 416 * 128) + 6
    mask[max(0, y1):min(128, y2), max(0, x1):min(128, x2)] = False
    px = arr[mask]
    r_, g_, b_ = px[:, 0], px[:, 1], px[:, 2]
    v = px.max(1); mn = px.min(1); s = np.where(v > 0, (v - mn) / np.maximum(v, 1), 0)
    hist, _ = np.histogram(v, bins=8, range=(0, 255), density=True)
    gray = arr.mean(2)
    gx = np.abs(np.diff(gray, axis=1)); gy = np.abs(np.diff(gray, axis=0))
    edge = float(((gx > 20).mean() + (gy > 20).mean()) / 2)
    f = [r_.mean(), g_.mean(), b_.mean(), r_.std(), g_.std(), b_.std(),
         float(v.mean()), float(v.std()), float(s.mean()), edge, *hist.tolist()]
    feats.append(f); meta.append({"id": r["sampleId"], "cls": cls, "path": r["storageKey"]})
X = np.array(feats); X = (X - X.mean(0)) / (X.std(0) + 1e-6)

def kmeans(X, k, seed=7020, iters=200):
    rng = np.random.default_rng(seed)
    centers = X[rng.choice(len(X), k, replace=False)]
    for _ in range(iters):
        d = ((X[:, None, :] - centers[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        new = np.array([X[lab == i].mean(0) if (lab == i).any() else centers[i] for i in range(k)])
        if np.allclose(new, centers): break
        centers = new
    return lab
labels = kmeans(X, 5)
import json as _json
(ROOT / "temporary/model_train_20261018/scene_groups.json").write_text(_json.dumps({m["id"]: int(l) for m, l in zip(meta, labels)}, ensure_ascii=False, indent=1), encoding="utf-8")
for k in range(5):
    idx = np.where(labels == k)[0]
    cls = [meta[i]["cls"] for i in idx]
    print(f"group {k}: n={len(idx)} class0={cls.count(0)} class1={cls.count(1)} ids={[meta[i]['id'][:8] for i in idx]}")
# contact sheet sorted by group
cell = 180; cols = 10
order = sorted(range(len(meta)), key=lambda i: (labels[i], meta[i]["cls"], meta[i]["id"]))
sheet = Image.new("RGB", (cols * cell, ((len(order) + cols - 1) // cols) * cell), (20, 20, 20))
from PIL import ImageDraw
for pos, i in enumerate(order):
    im = Image.open(ROOT / "data/storage" / meta[i]["path"]).convert("RGB").resize((cell, cell))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, cell - 1, 18], fill=(0, 0, 0))
    d.text((3, 2), f"g{labels[i]} c{meta[i]['cls']} {meta[i]['id'][:6]}", fill=(255, 255, 0))
    sheet.paste(im, ((pos % cols) * cell, (pos // cols) * cell))
sheet.save(ROOT / "temporary/model_train_20261018/scene_groups.jpg", quality=88)
print("saved scene_groups.jpg")
