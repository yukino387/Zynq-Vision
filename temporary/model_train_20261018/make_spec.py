"""Build a training spec directly from the platform DB for the annotated board samples."""
import hashlib, json, sqlite3
from pathlib import Path

DB = Path(r"C:/00_workplace/fpga/cnn_accelerator/data/app.db")
STORAGE = Path(r"C:/00_workplace/fpga/cnn_accelerator/data/storage")
OUT = Path(__file__).parent
VERSION = "INT8-EARPHONE-20261018"
CLASSES = ["正面", "反面", "_unused_2", "_unused_3", "_unused_4", "_unused_5"]

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
rows = c.execute("""
  select s.id sid, s.createdAt, a.storageKey, a.sha256
  from Sample s join Asset a on a.sampleId = s.id
  where a.kind='RAW' and a.format='RGB565_LE' and a.deletedAt is null and s.deletedAt is null
    and s.id in (
      select sampleId from AnnotationSet
      where status='COMPLETE'
        and version=(select max(version) from AnnotationSet z
                     where z.sampleId=AnnotationSet.sampleId and z.status='COMPLETE'))
  order by s.createdAt, s.id
""").fetchall()

items = []
for index, r in enumerate(rows):
    boxes = c.execute("""
      select b.classId, b.x1, b.y1, b.x2, b.y2
      from Annotation b join AnnotationSet a on a.id=b.setId
      where a.sampleId=? and a.status='COMPLETE'
        and a.version=(select max(version) from AnnotationSet z
                       where z.sampleId=? and z.status='COMPLETE')
    """, (r["sid"], r["sid"])).fetchall()
    split = "val" if index % 4 == 3 else "train"   # spread 4 held-out frames across the capture
    items.append({
        "id": r["sid"],
        "path": str(STORAGE / r["storageKey"]),
        "sha256": r["sha256"],
        "raw": True,
        "width": 416, "height": 416,
        "split": split,
        "boxes": [{"classId": b["classId"], "x1": b["x1"], "y1": b["y1"],
                   "x2": b["x2"], "y2": b["y2"]} for b in boxes],
    })

checksum = hashlib.sha256(json.dumps(
    [{"sampleId": i["id"], "split": i["split"], "snapshot": {"boxes": i["boxes"]}} for i in items],
    sort_keys=True).encode()).hexdigest()

spec = {
    "options": {"colorMode": "GRAY", "epochs": 200, "batchSize": 8,
                "learningRate": 0.001, "seed": 7020, "device": "cuda",
                "amp": True, "workers": 0},
    "items": items,
    "version": VERSION,
    "classes": CLASSES,
    "datasetChecksum": checksum,
}
(OUT / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(items)} items -> train {sum(i['split']=='train' for i in items)}, "
      f"val {sum(i['split']=='val' for i in items)}")
print(f"classes/ids: {[i['id'] for i in items]}")
