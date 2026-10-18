"""Per-image loss decomposition and confidence at the assigned positive cell."""
import json, math, sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from data import Samples
from detection import ANCHORS, decode, iou, loss
from pl_model import FixedGraph, OUTPUT_SCALES

run = Path(sys.argv[1]); spec_path = Path(sys.argv[2])
spec = json.loads(spec_path.read_text(encoding="utf-8"))
split = sys.argv[3] if len(sys.argv) > 3 else "val"
items = [i for i in spec["items"] if i["split"] == split]
model = FixedGraph(1)
model.load_state_dict(torch.load(run / "checkpoint.pt", weights_only=True, map_location="cpu")["state_dict"])
model.eval(); data = Samples(items, "GRAY")
anchors = [(h, a, w / size, height / size) for h, size in enumerate((7, 14)) for a, (w, height) in enumerate(ANCHORS[h])]
with torch.no_grad():
    for index in range(len(data)):
        x, boxes = data[index]
        outs = model(x[None])
        print("image", index, "total loss", round(float(loss(outs, boxes[None])), 3))
        for cls, x1, y1, x2, y2 in boxes.tolist():
            xc, yc, w, h = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
            ranked = sorted(anchors, reverse=True, key=lambda a: min(w, a[2]) * min(h, a[3]) / (w * h + a[2] * a[3] - min(w, a[2]) * min(h, a[3])))
            hi, ai, aw, ah = ranked[0]
            size = 7 if hi == 0 else 14
            row, col = min(int(yc * size), size - 1), min(int(xc * size), size - 1)
            logits = outs[hi][0].reshape(3, 11, size, size)[ai, :, row, col]
            obj = float(torch.sigmoid(logits[4]))
            probs = torch.sigmoid(logits[5:]); best = int(probs.argmax())
            print(f"  gt cls {int(cls)} anchor L{hi}:{ai} cell({row},{col}) obj={obj:.3f} "
                  f"cls{best}={float(probs[best]):.3f} gtcls={float(probs[int(cls)]):.3f} "
                  f"xy={logits[:2].tolist()} wh={logits[2:4].tolist()}")
        for th in (0.05, 0.1, 0.2, 0.35):
            pred = decode([o[0] * s for o, s in zip(outs, OUTPUT_SCALES)], threshold=th)
            print(f"  thr {th}: {len(pred)} dets", [round(p[0], 3) for p in pred[:3]])
