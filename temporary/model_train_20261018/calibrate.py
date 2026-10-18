"""Post-hoc objectness/class bias calibration to use the board's 0.35 threshold."""
import json, shutil, sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from data import Samples
from detection import decode, metrics
from pl_model import FixedGraph, HEADS, OUTPUT_SCALES, export_int8, integer_forward

run = Path(sys.argv[1]); spec_path = Path(sys.argv[2])
spec = json.loads(spec_path.read_text(encoding="utf-8"))
items = [i for i in spec["items"] if i["split"] == "val"]
model = FixedGraph(1)
model.load_state_dict(torch.load(run / "checkpoint.pt", weights_only=True, map_location="cpu")["state_dict"])
model.eval()
weights = (run / "weights.bin").read_bytes(); metadata = (run / "metadata.bin").read_bytes()
data = Samples(items, "GRAY")
outputs, labels = [], []
for index in range(len(data)):
    x, boxes = data[index]
    integer = integer_forward(model, torch.round(x * 127)[None], weights, metadata)
    outputs.append([v[0].float() * s for v, s in zip(integer, OUTPUT_SCALES)])
    labels.append(boxes)

def shifted(entry, d_obj, d_cls):
    out = []
    for head in entry:
        v = head.reshape(3, 11, *head.shape[1:]).clone()
        v[:, 4] += d_obj
        v[:, 5:] += d_cls
        out.append(v.reshape(head.shape))
    return out

best = None
for d_obj in (0, .5, 1., 1.5, 2., 2.5, 3.):
    for d_cls in (0, .5, 1., 1.5, 2.):
        preds = [decode(shifted(e, d_obj, d_cls), threshold=.05) for e in outputs]
        m = metrics(preds, labels)
        dets = [sum(1 for p in pred if p[0] >= .35) for pred in preds]
        f1 = 2 * (m["precision"] or 0) * (m["recall"] or 0) / ((m["precision"] or 0) + (m["recall"] or 0)) if (m["precision"] or 0) + (m["recall"] or 0) else 0
        print(f"d_obj={d_obj:.1f} d_cls={d_cls:.1f} mAP={m['mAP50']} P={m['precision']:.2f} R={m['recall']} "
              f"dets>=.35={dets} F1={f1:.2f}", flush=True)
        if best is None or f1 > best[0] or (f1 == best[0] and d_obj + d_cls < best[1] + best[2]):
            best = (f1, d_obj, d_cls)
print("best", best)
if best[0] <= 0:
    print("no candidate reaches 0.35; calibration skipped"); sys.exit(1)
f1, d_obj, d_cls = best
with torch.no_grad():
    for head in HEADS:
        bias = model.layers[str(head)].bias.view(3, 11)
        bias[:, 4] += d_obj
        bias[:, 5:] += d_cls
out = run.parent / (run.name + "cal")
out.mkdir(exist_ok=True)
for name in ("weights.bin", "metadata.bin", "model.bin", "manifest.json", "report.json", "quantization.json"):
    shutil.copy2(run / name, out / name)
torch.save({"state_dict": model.state_dict(), "options": spec["options"], "epoch": 0, "calibration": best}, out / "checkpoint.pt")
hidden_scale = json.loads((run / "report.json").read_text(encoding="utf-8"))["hiddenScale"]
weights2, metadata2, manifest = export_int8(model, hidden_scale, spec["version"], out)
manifest["classes"] = spec["classes"]
(out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
report = json.loads((run / "report.json").read_text(encoding="utf-8"))
report["calibration"] = {"objectnessBias": d_obj, "classBias": d_cls, "threshold": .35}
(out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", out)
