"""Build a full FP32 FixedGraph(3) from MILK-RGB, keeping objectness/box heads, resetting class heads."""
import sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from pl_model import FixedGraph, HEADS, OUTPUT_SCALES, unpack_weights
PKG = ROOT / "data/storage/models/65ce8fc8-29a6-4ff9-b85e-53e95c3c636c"
OUT = ROOT / "temporary/model_train_20261018/source_rgb_fp32.pt"
HS = 0.075
pkg = PKG.read_bytes(); weights = pkg[128:128 + 6350208]
metadata = np.frombuffer(pkg[128 + 6350208:], dtype="<i4")
model = FixedGraph(3); state = model.state_dict()
for index, (_, _, woff, moff, ci, co, _, _, kernel, act) in enumerate(model.commands):
    if kernel not in (1, 3): continue
    ratio = metadata[moff + co:moff + 2 * co].astype(np.float64) / np.exp2(metadata[moff + 2 * co:moff + 3 * co].astype(np.float64))
    if index == 0:
        ws, input_scale = ratio * 127 * HS, 1 / 127
    elif index in HEADS:
        ws, input_scale = ratio * OUTPUT_SCALES[HEADS.index(index)] / HS, HS
    else:
        ws, input_scale = ratio, HS
    length = ((co + 47) // 48 * 48) * ((ci + 7) // 8 * 8) * kernel**2
    int8 = unpack_weights(weights[woff:woff + length], int(co), int(ci), int(kernel)).astype(np.float64)
    state[f"layers.{index}.weight"] = torch.from_numpy((int8 * ws[:, None, None, None]).astype(np.float32))
    state[f"layers.{index}.bias"] = torch.from_numpy((metadata[moff:moff + co].astype(np.float64) * (input_scale * ws)).astype(np.float32))

# Keep objectness/box channels (0:5 per anchor); reset class channels (5:11 per anchor).
for head in HEADS:
    w, b = state[f"layers.{head}.weight"], state[f"layers.{head}.bias"]
    for anchor in range(3):
        sl = slice(anchor * 11 + 5, anchor * 11 + 11)
        w[sl] = torch.randn_like(w[sl]) * 0.01
        b[sl] = 0
torch.save({"state_dict": state, "options": {"colorMode": "RGB"}, "epoch": 0,
            "source": "MILK-RGB-20261017@65ce8fc8", "hiddenScale": HS}, OUT)
print("saved", OUT, OUT.stat().st_size)
