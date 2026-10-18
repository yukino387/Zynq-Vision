import sqlite3, sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from data import preprocess
from detection import decode, iou
from pl_model import FixedGraph, OUTPUT_SCALES, integer_forward
PKG = ROOT / "data/storage/models/65ce8fc8-29a6-4ff9-b85e-53e95c3c636c"
weights = PKG.read_bytes()[128:128 + 6350208]; metadata = PKG.read_bytes()[128 + 6350208:]
c = sqlite3.connect(ROOT / "data/app.db"); c.row_factory = sqlite3.Row
rows = c.execute("""select i.sampleId,i.snapshot,a.storageKey from DatasetItem i join Asset a on a.sampleId=i.sampleId
 where i.datasetId='cmvd7apcz0163uea43cbxudgt' and a.kind='RAW' and a.format='RGB565_LE' and a.deletedAt is null
 order by i.sampleId limit 6""").fetchall()
model = FixedGraph(3)
for r in rows:
    snap = __import__("json").loads(r["snapshot"]); gt = snap["boxes"][0]
    gcls = gt["classId"]; gbox = np.array([gt["x1"]/416, gt["y1"]/416, gt["x2"]/416, gt["y2"]/416])
    x = preprocess(ROOT / "data/storage" / r["storageKey"], "RGB", raw=True)
    out = integer_forward(model, x[None].to(torch.int64), weights, metadata)
    pred = decode([o[0].float() * s for o, s in zip(out, OUTPUT_SCALES)], threshold=.35)
    best = max(((iou(bb, gbox), score, cls) for score, cls, bb in pred), default=(0, 0, -1))
    print(r["sampleId"][:10], "gt", gcls, "dets", len(pred), "bestIoU", round(best[0],3), "score", round(best[1],3), "cls", best[2])
