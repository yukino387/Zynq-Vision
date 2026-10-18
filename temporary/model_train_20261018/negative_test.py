"""Run the trained package on non-earphone board frames and count detections."""
import json, sqlite3, sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from data import preprocess
from detection import decode
from pl_model import FixedGraph, OUTPUT_SCALES, integer_forward
run = Path(sys.argv[1])
c = sqlite3.connect(ROOT / "data/app.db"); c.row_factory = sqlite3.Row
rows = c.execute("""select s.id sid, a.storageKey from Sample s join Asset a on a.sampleId=s.id
  where s.source='BOARD' and s.taskId is not 'cmvctfolq001aueqgb9y0xzz7'
    and a.kind='RAW' and a.format='RGB565_LE' and a.deletedAt is null and s.deletedAt is null
  order by s.createdAt""").fetchall()
model = FixedGraph(1)
weights = (run / "weights.bin").read_bytes(); metadata = (run / "metadata.bin").read_bytes()
for r in rows:
    x = preprocess(ROOT / "data/storage" / r["storageKey"], "GRAY", raw=True)
    out = integer_forward(model, torch.round(x.float() / 127 * 127)[None], weights, metadata)
    pred = decode([v[0].float() * s for v, s in zip(out, OUTPUT_SCALES)], threshold=.05)
    print(r["sid"][:10], "max", round(max([p[0] for p in pred] or [0]), 3),
          ">=.35", sum(p[0] >= .35 for p in pred), "dets", [(round(p[0], 2), p[1]) for p in pred[:3]])
