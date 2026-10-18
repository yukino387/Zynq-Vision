"""Evaluate a two-class box model: detection metrics plus class accuracy/confusion."""
import json, sys
from pathlib import Path
import numpy as np, torch
from PIL import Image, ImageDraw
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from data import Samples
from detection import decode, iou, metrics
from pl_model import FixedGraph, OUTPUT_SCALES, integer_forward

run = Path(sys.argv[1]); spec_path = Path(sys.argv[2])
spec = json.loads(spec_path.read_text(encoding="utf-8"))
split = sys.argv[3] if len(sys.argv) > 3 else "val"
items = [i for i in spec["items"] if i["split"] == split]
model = FixedGraph(1 if spec["options"]["colorMode"] == "GRAY" else 3)
model.load_state_dict(torch.load(run / "checkpoint.pt", weights_only=True, map_location="cpu")["state_dict"])
model.eval()
weights = (run / "weights.bin").read_bytes(); metadata = (run / "metadata.bin").read_bytes()
data = Samples(items, spec["options"]["colorMode"])
preds, labels = [], []
cell = 260
sheet = Image.new("RGB", (len(items) * cell, cell), (20, 20, 20))
correct = 0; conf = np.zeros((2, 3), dtype=int)  # gt x (pred0, pred1, none)
for index in range(len(data)):
    x, boxes = data[index]
    integer = integer_forward(model, torch.round(x * 127)[None], weights, metadata)
    outs = [v[0].float() * s for v, s in zip(integer, OUTPUT_SCALES)]
    pred = decode(outs, threshold=0.05)
    preds.append(pred); labels.append(boxes)
    gt = boxes[0]; gcls = int(gt[0]); gbox = gt[1:].numpy()
    best = None
    for score, cls, box in pred:
        if score < 0.35: continue
        v = iou(box, gbox)
        if v >= 0.5 and (best is None or score > best[0]): best = (score, cls, box)
    pcls = best[1] if best else -1
    conf[gcls, pcls if pcls >= 0 else 2] += 1
    if pcls == gcls: correct += 1
    p = np.frombuffer(Path(items[index]["path"]).read_bytes(), dtype="<u2").reshape(416, 416)
    r, g, b = p >> 11, (p >> 5) & 63, p & 31
    rgb = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), 2).astype(np.uint8)
    im = Image.fromarray(rgb).resize((cell, cell)); d = ImageDraw.Draw(im)
    for score, cls, bb in pred[:5]:
        col = (0, 255, 0) if cls == 0 else (255, 128, 0)
        d.rectangle([bb[0] * cell, bb[1] * cell, bb[2] * cell, bb[3] * cell], outline=col, width=2)
        d.text((bb[0] * cell + 2, bb[1] * cell + 2), f"{cls}:{score:.2f}", fill=col)
    d.rectangle([gbox[0] * cell, gbox[1] * cell, gbox[2] * cell, gbox[3] * cell], outline=(0, 200, 255), width=1)
    d.text((4, 4), f"GT {gcls} -> {pcls if pcls>=0 else 'none'}", fill=(255, 255, 0))
    sheet.paste(im, (index * cell, 0))
sheet.save(run / f"{split}_class_predictions.jpg", quality=92)
print("class accuracy", correct, "/", len(items), "=", round(correct / len(items), 3))
print("confusion rows=GT [pred0,pred1,none]:\n", conf)
print(json.dumps(metrics(preds, labels), ensure_ascii=False, indent=1))
