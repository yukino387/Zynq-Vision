"""Evaluate a run at several confidence thresholds and save INT8 logits for calibration."""
import json, sys
from pathlib import Path
import numpy as np, torch
from PIL import Image, ImageDraw
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from data import Samples
from detection import decode, metrics
from pl_model import FixedGraph, OUTPUT_SCALES, integer_forward

run = Path(sys.argv[1])
spec_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "temporary/model_train_20261018/spec2.json"
spec = json.loads(spec_path.read_text(encoding="utf-8"))
split = sys.argv[3] if len(sys.argv) > 3 else "val"
items = [i for i in spec["items"] if i["split"] == split]
model = FixedGraph(1)
ckpt = torch.load(run / "checkpoint.pt", weights_only=True, map_location="cpu")
model.load_state_dict(ckpt["state_dict"]); model.eval()
weights = (run / "weights.bin").read_bytes(); metadata = (run / "metadata.bin").read_bytes()
data = Samples(items, "GRAY")
logits, labels = [], []
for index in range(len(data)):
    x, boxes = data[index]
    integer = integer_forward(model, torch.round(x * 127)[None], weights, metadata)
    outs = [v[0].float() * s for v, s in zip(integer, OUTPUT_SCALES)]
    logits.append([o for o in outs]); labels.append(boxes.numpy())
np.savez(run / f"logits_{split}.npz", **{f"o{i}_{j}": logits[j][i].numpy() for j in range(len(items)) for i in range(2)})
for threshold in (0.05, 0.1, 0.2, 0.3, 0.35, 0.5):
    preds, labs = [], []
    for entry, box in zip(logits, labels):
        preds.append(decode([entry[0][None], entry[1][None]], threshold=threshold)); labs.append(torch.from_numpy(box))
    m = metrics(preds, labs)
    top = max([p[0] for p in preds[0]] or [0])
    print(f"thr={threshold}: mAP50={m['mAP50']} precision={m['precision']:.3f} recall={m['recall']} "
          f"dets={[len(p) for p in preds]} top0={top:.3f}")
# draw at 0.2
sheet = Image.new("RGB", (len(items) * 260, 260), (20, 20, 20))
for index, (entry, box) in enumerate(zip(logits, labels)):
    p = np.frombuffer(Path(items[index]["path"]).read_bytes(), dtype="<u2").reshape(416, 416)
    r, g, b = p >> 11, (p >> 5) & 63, p & 31
    rgb = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), 2).astype(np.uint8)
    im = Image.fromarray(rgb).resize((260, 260)); d = ImageDraw.Draw(im)
    pred = decode([entry[0][None], entry[1][None]], threshold=0.1)
    for score, cls, bb in pred[:6]:
        col = (0, 255, 0) if score >= 0.35 else (255, 255, 0)
        d.rectangle([bb[0] * 260, bb[1] * 260, bb[2] * 260, bb[3] * 260], outline=col, width=2)
        d.text((bb[0] * 260 + 2, bb[1] * 260 + 2), f"{score:.2f}", fill=col)
    t = box[0]
    d.rectangle([t[1] * 260, t[2] * 260, t[3] * 260, t[4] * 260], outline=(255, 128, 0), width=1)
    sheet.paste(im, (index * 260, 0))
sheet.save(run / f"{split}_predictions.jpg", quality=92)
print("saved", run / f"{split}_predictions.jpg")
