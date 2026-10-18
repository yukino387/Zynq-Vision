"""Verify: (1) FP32 reconstruction fidelity vs MILK-RGB INT8; (2) source detection on the 60 new frames."""
import json, sqlite3, sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from data import preprocess
from detection import decode, iou
from pl_model import FixedGraph, OUTPUT_SCALES, integer_forward

PKG = ROOT / "data/storage/models/65ce8fc8-29a6-4ff9-b85e-53e95c3c636c"
pkg = PKG.read_bytes(); weights = pkg[128:128 + 6350208]; metadata = pkg[128 + 6350208:]
source = FixedGraph(3)
recon = FixedGraph(3)
recon.load_state_dict(torch.load(ROOT / "temporary/model_train_20261018/source_rgb_fp32.pt", weights_only=True)["state_dict"])
recon.eval()

c = sqlite3.connect(ROOT / "data/app.db"); c.row_factory = sqlite3.Row
rows = c.execute("""select i.sampleId,i.snapshot,a.storageKey from DatasetItem i join Asset a on a.sampleId=i.sampleId
 where i.datasetId='cmvd7apcz0163uea43cbxudgt' and a.kind='RAW' and a.format='RGB565_LE' and a.deletedAt is null
 order by i.sampleId""").fetchall()

fid_err, fid_corr = [], []
stats = {0: {"n": 0, "hit35": 0, "hit20": 0, "ious": [], "scores": [], "fp35": 0},
         1: {"n": 0, "hit35": 0, "hit20": 0, "ious": [], "scores": [], "fp35": 0}}
for r in rows:
    snap = json.loads(r["snapshot"]); gt = snap["boxes"][0]; gcls = int(gt["classId"])
    gbox = np.array([gt["x1"]/416, gt["y1"]/416, gt["x2"]/416, gt["y2"]/416])
    x = preprocess(ROOT / "data/storage" / r["storageKey"], "RGB", raw=True)
    out = integer_forward(source, x[None].to(torch.int64), weights, metadata)
    ref = [o[0].float() * s for o, s in zip(out, OUTPUT_SCALES)]
    with torch.no_grad():
        fp = recon((x.float() / 127)[None])
    # fidelity on objectness + box channels only (class head was reset)
    for h in range(2):
        a = fp[h][0][[0,1,2,3,4]].flatten(); b = ref[h][[0,1,2,3,4]].flatten()
        fid_err.append(float((a-b).abs().mean())); fid_corr.append(float(torch.corrcoef(torch.stack([a,b]))[0,1]))
    pred35 = decode([o.clone() for o in ref], threshold=.35)
    pred20 = decode([o.clone() for o in ref], threshold=.20)
    best = max(((iou(bb, gbox), score, cls) for score, cls, bb in pred35), default=(0,0,-1))
    best20 = max(((iou(bb, gbox), score, cls) for score, cls, bb in pred20), default=(0,0,-1))
    s = stats[gcls]; s["n"] += 1
    s["ious"].append(best[0]); s["scores"].append(best[1])
    if best[0] >= .5: s["hit35"] += 1
    if best20[0] >= .5: s["hit20"] += 1
    s["fp35"] += sum(1 for score, cls, bb in pred35 if iou(bb, gbox) < .5)
print(f"reconstruction: mean|err|={np.mean(fid_err):.3f} mean corr={np.mean(fid_corr):.3f} min corr={np.min(fid_corr):.3f}")
for cls, s in stats.items():
    print(f"class {cls} n={s['n']} hit@0.35={s['hit35']} hit@0.20={s['hit20']} "
          f"meanIoU={np.mean(s['ious']):.3f} maxIoU={np.max(s['ious']):.3f} "
          f"meanScore={np.mean(s['scores']):.3f} fp@0.35={s['fp35']}")
