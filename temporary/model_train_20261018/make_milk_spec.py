"""Build a training spec from the new beverage-box dataset (60 items, 2 classes)."""
import hashlib, json, sqlite3
from pathlib import Path

ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
DB = ROOT / "data/app.db"
OUT = ROOT / "temporary/model_train_20261018"
DSID = "cmvd7apcz0163uea43cbxudgt"
VERSION = "INT8-MILK-STRAW-20261018"
CLASSES = ["正常", "不正常", "_unused_2", "_unused_3", "_unused_4", "_unused_5"]

c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
rows = c.execute("""
  select i.sampleId, i.snapshot, s.createdAt
  from DatasetItem i join Sample s on s.id=i.sampleId
  where i.datasetId=? order by s.createdAt, i.sampleId""", (DSID,)).fetchall()

items = []
for r in rows:
    snap = json.loads(r["snapshot"])
    raw = c.execute("""select storageKey,sha256,size from Asset
      where sampleId=? and kind='RAW' and format='RGB565_LE' and deletedAt is null""",
      (r["sampleId"],)).fetchone()
    if not raw:
        raise SystemExit(f"no RAW for {r['sampleId']}")
    path = ROOT / "data/storage" / raw["storageKey"]
    if path.stat().st_size != 416 * 416 * 2:
        raise SystemExit(f"bad RAW size {path}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != raw["sha256"]:
        raise SystemExit(f"RAW sha mismatch {path}")
    boxes = []
    for b in snap["boxes"]:
        x1, y1, x2, y2 = float(b["x1"]), float(b["y1"]), float(b["x2"]), float(b["y2"])
        if not (0 <= x1 < x2 <= 416 and 0 <= y1 < y2 <= 416):
            raise SystemExit(f"bad box {r['sampleId']} {b}")
        boxes.append({"classId": int(b["classId"]), "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    if len(boxes) != 1:
        raise SystemExit(f"expected 1 box, got {len(boxes)} for {r['sampleId']}")
    items.append({"id": r["sampleId"], "path": str(path), "sha256": raw["sha256"],
                  "raw": True, "width": 416, "height": 416, "boxes": boxes,
                  "_cls": boxes[0]["classId"], "_t": r["createdAt"]})

# Hold out the last 6 captures of each class (different end-of-session scenes).
for cls in (0, 1):
    group = [it for it in items if it["_cls"] == cls]
    for it in group[-6:]:
        it["split"] = "val"
for it in items:
    if "split" not in it:
        it["split"] = "train"

checksum = hashlib.sha256(json.dumps(
    [{"sampleId": it["id"], "split": it["split"], "snapshot": {"boxes": it["boxes"]}} for it in items],
    sort_keys=True).encode()).hexdigest()
for it in items:
    it.pop("_cls"); it.pop("_t")
spec = {"options": {"colorMode": "GRAY", "epochs": 300, "batchSize": 4,
                    "learningRate": 0.001, "seed": 7020, "device": "cuda",
                    "amp": True, "workers": 0},
        "items": items, "version": VERSION, "classes": CLASSES,
        "datasetChecksum": checksum}
(OUT / "milk_spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
from collections import Counter
print("items", len(items), Counter((it["split"], next(b["classId"] for b in it["boxes"])) for it in items))
print("train", sum(it["split"] == "train" for it in items), "val", sum(it["split"] == "val" for it in items))
print("version", VERSION)
