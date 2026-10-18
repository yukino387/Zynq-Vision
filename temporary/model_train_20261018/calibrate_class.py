"""Post-hoc objectness/class bias calibration for the 2-class milk model."""
import json, shutil, sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from data import Samples
from detection import decode, iou
from pl_model import FixedGraph, HEADS, OUTPUT_SCALES, export_int8, integer_forward

run = Path(sys.argv[1]); spec_path = Path(sys.argv[2]); split = sys.argv[3] if len(sys.argv) > 3 else "train"
spec = json.loads(spec_path.read_text(encoding="utf-8"))
items = [i for i in spec["items"] if i["split"] == split]
model = FixedGraph(1 if spec["options"]["colorMode"] == "GRAY" else 3)
model.load_state_dict(torch.load(run / "checkpoint.pt", weights_only=True, map_location="cpu")["state_dict"])
model.eval()
weights = (run / "weights.bin").read_bytes(); metadata = (run / "metadata.bin").read_bytes()
data = Samples(items, spec["options"]["colorMode"])
logits, labels = [], []
for index in range(len(data)):
    x, boxes = data[index]
    integer = integer_forward(model, torch.round(x * 127)[None], weights, metadata)
    logits.append([v[0].float() * s for v, s in zip(integer, OUTPUT_SCALES)]); labels.append(boxes)

def shifted(entry, d_obj, d_cls):
    out = []
    for head in entry:
        v = head.reshape(3, 11, *head.shape[1:]).clone()
        v[:, 4] += d_obj; v[:, 5:] += d_cls
        out.append(v.reshape(head.shape))
    return out

def score_combo(d_obj, d_cls, threshold=.35):
    correct = fp = missed = 0
    for entry, gtboxes in zip(logits, labels):
        pred = decode(shifted(entry, d_obj, d_cls), threshold=.05)
        gt = gtboxes[0]
        gcls = int(gt[0]); gbox = gt[1:].numpy()
        best = None; extra = 0
        for score, cls, box in pred:
            if score < threshold: continue
            v = iou(box, gbox)
            if v >= .5:
                if best is None or score > best[0]: best = (score, cls)
                else: extra += 1
            else: extra += 1
        if best is None: missed += 1
        elif best[1] == gcls: correct += 1
        else: missed += 1
        fp += extra
    return correct, fp, missed

best = None
for d_obj in (0, .5, 1., 1.5, 2., 2.5, 3., 4.):
    for d_cls in (0, .5, 1., 1.5, 2.):
        c, fp, m = score_combo(d_obj, d_cls)
        value = c - 0.5 * fp
        print(f"d_obj={d_obj:.1f} d_cls={d_cls:.1f} correct={c}/{len(items)} fp={fp} missed={m} value={value:.1f}", flush=True)
        if best is None or value > best[0]: best = (value, d_obj, d_cls, c, fp, m)
print("BEST", best)
if best[3] == 0: sys.exit(1)
_, d_obj, d_cls, c, fp, m = best
with torch.no_grad():
    for head in HEADS:
        bias = model.layers[str(head)].bias.view(3, 11)
        bias[:, 4] += d_obj; bias[:, 5:] += d_cls
out = run.parent / (run.name + "cal"); out.mkdir(exist_ok=True)
for name in ("weights.bin", "metadata.bin", "model.bin", "manifest.json", "report.json", "quantization.json"):
    shutil.copy2(run / name, out / name)
torch.save({"state_dict": model.state_dict(), "options": spec["options"], "epoch": 0,
            "calibration": {"objectnessBias": d_obj, "classBias": d_cls}}, out / "checkpoint.pt")
hidden_scale = json.loads((run / "report.json").read_text(encoding="utf-8"))["hiddenScale"]
weights2, metadata2, manifest = export_int8(model, hidden_scale, spec["version"], out)
manifest["classes"] = spec["classes"]
(out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
report = json.loads((run / "report.json").read_text(encoding="utf-8"))
report["calibration"] = {"objectnessBias": d_obj, "classBias": d_cls, "threshold": .35,
                         "correct": c, "falsePositive": fp, "missed": m, "split": split}
(out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", out)
