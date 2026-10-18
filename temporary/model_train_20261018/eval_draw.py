"""Draw INT8-reference predictions for the validation split of a training run."""
import json, sys
from pathlib import Path
import numpy as np, torch
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(r"C:/00_workplace/fpga/cnn_accelerator/camera/training")))
from data import Samples
from detection import decode, metrics
from pl_model import FixedGraph, OUTPUT_SCALES, integer_forward

run = Path(sys.argv[1])
spec = json.loads(Path(sys.argv[2] if len(sys.argv) > 2 else r"C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018/spec.json").read_text(encoding="utf-8"))
val = [i for i in spec["items"] if i["split"] == "val"]
model = FixedGraph(1)
ckpt = torch.load(run / "checkpoint.pt", weights_only=True, map_location="cpu")
model.load_state_dict(ckpt["state_dict"]); model.eval()
weights = (run / "weights.bin").read_bytes(); metadata = (run / "metadata.bin").read_bytes()
data = Samples(val, "GRAY")
predictions, labels = [], []
sheet = Image.new("RGB", (len(val) * 260, 260), (20, 20, 20)); d = ImageDraw.Draw(sheet)
for index in range(len(data)):
    x, boxes = data[index]
    integer = integer_forward(model, torch.round(x * 127)[None], weights, metadata)
    outputs = [v[0].float() * s for v, s in zip(integer, OUTPUT_SCALES)]
    pred = decode(outputs, threshold=0.05)
    predictions.append(pred); labels.append(boxes)
    pixels = np.frombuffer(Path(val[index]["path"]).read_bytes(), dtype="<u2").reshape(416, 416)
    r, g, b = pixels >> 11, (pixels >> 5) & 63, pixels & 31
    rgb = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), 2).astype(np.uint8)
    im = Image.fromarray(rgb).resize((260, 260)); dd = ImageDraw.Draw(im)
    for score, cls, box in pred[:8]:
        color = (0, 255, 0) if score >= 0.35 else (255, 255, 0)
        dd.rectangle([box[0] * 260, box[1] * 260, box[2] * 260, box[3] * 260], outline=color, width=2)
        dd.text((box[0] * 260 + 3, box[1] * 260 + 3), f"{score:.2f}", fill=color)
    print(Path(val[index]["path"]).name, [round(float(p[0]), 3) for p in pred[:3]])
    for row in boxes:
        x1, y1, x2, y2 = [float(v) * 260 for v in row[1:]]
        dd.rectangle([x1, y1, x2, y2], outline=(255, 128, 0), width=1)
    sheet.paste(im, (index * 260, 0))
sheet.save(run / "val_predictions.jpg", quality=92)
print(json.dumps(metrics(predictions, labels), ensure_ascii=False, indent=1))
