"""Sweep hidden_scale for the MILK-RGB reconstruction and match its INT8 outputs."""
import sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from data import preprocess
from pl_model import FixedGraph, HEADS, OUTPUT_SCALES, unpack_weights, integer_forward

PKG = ROOT / "data/storage/models/65ce8fc8-29a6-4ff9-b85e-53e95c3c636c"
WEIGHT_BYTES = 6350208
pkg = PKG.read_bytes(); weights = pkg[128:128 + WEIGHT_BYTES]
metadata = np.frombuffer(pkg[128 + WEIGHT_BYTES:], dtype="<i4")
model = FixedGraph(3)

def build(hs):
    state = model.state_dict()
    for index, (_, _, woff, moff, ci, co, _, _, kernel, act) in enumerate(model.commands):
        if kernel not in (1, 3): continue
        mult = metadata[moff + co:moff + 2 * co].astype(np.float64)
        shift = metadata[moff + 2 * co:moff + 3 * co].astype(np.float64)
        ratio = mult / np.exp2(shift)
        if index == 0:
            ws = ratio * 127 * hs; input_scale = 1 / 127
        elif index in HEADS:
            ws = ratio * OUTPUT_SCALES[HEADS.index(index)] / hs; input_scale = hs
        else:
            ws = ratio; input_scale = hs
        length = ((co + 47) // 48 * 48) * ((ci + 7) // 8 * 8) * kernel**2
        int8 = unpack_weights(weights[woff:woff + length], int(co), int(ci), int(kernel)).astype(np.float64)
        state[f"layers.{index}.weight"] = torch.from_numpy((int8 * ws[:, None, None, None]).astype(np.float32))
        bias = metadata[moff:moff + co].astype(np.float64) * (input_scale * ws)
        state[f"layers.{index}.bias"] = torch.from_numpy(bias.astype(np.float32))
    return state

# source INT8 reference on 3 dataset images
import sqlite3
c = sqlite3.connect(ROOT / "data/app.db"); c.row_factory = sqlite3.Row
rows = c.execute("""select i.sampleId,a.storageKey from DatasetItem i join Asset a on a.sampleId=i.sampleId
 where i.datasetId='cmvd7apcz0163uea43cbxudgt' and a.kind='RAW' and a.format='RGB565_LE' and a.deletedAt is null
 order by i.sampleId limit 3""").fetchall()
inputs = []
for r in rows:
    x = preprocess(ROOT / "data/storage" / r["storageKey"], "RGB", raw=True)
    inputs.append(x)
refs = []
for x in inputs:
    out = integer_forward(model, x[None].to(torch.int64), weights, metadata)
    refs.append([o[0].float() * s for o, s in zip(out, OUTPUT_SCALES)])

for hs in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.075, 0.09, 0.11, 0.13, 0.16, 0.2):
    model.load_state_dict(build(hs)); model.eval()
    errs = []; cors = []
    with torch.no_grad():
        for x, ref in zip(inputs, refs):
            fp = model((x.float() / 127)[None])
            for h in range(2):
                a = fp[h][0][[4, *range(5, 11)]].flatten(); b = ref[h][[4, *range(5, 11)]].flatten()
                errs.append(float((a - b).abs().mean()))
                cors.append(float(torch.corrcoef(torch.stack([a, b]))[0, 1]))
    print(f"hs={hs:.3f} mae={np.mean(errs):.3f} corr={np.mean(cors):.3f}", flush=True)
