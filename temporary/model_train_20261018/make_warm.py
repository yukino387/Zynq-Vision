"""Warm-start a FixedGraph from the GRAY MILK-W8A8 INT8 package that was running on the board."""
import json, sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from pl_model import FixedGraph, HEADS, commands_for, unpack_weights

PKG = ROOT / "data/storage/models/38285564-63db-45af-aa93-65c5ca4848b6"
OUT = ROOT / "temporary/model_train_20261018/warm.pt"
WEIGHT_BYTES = 6350208
pkg = PKG.read_bytes()
weights = pkg[128:128 + WEIGHT_BYTES]
metadata = np.frombuffer(pkg[128 + WEIGHT_BYTES:], dtype="<i4")
model = FixedGraph(1)
state = model.state_dict()
counts = {}
for index, (_, _, woff, moff, ci, co, _, _, kernel, act) in enumerate(model.commands):
    if kernel not in (1, 3) or index == 0 or index in HEADS:
        continue
    length = ((co + 47) // 48 * 48) * ((ci + 7) // 8 * 8) * kernel**2
    int8 = unpack_weights(weights[woff:woff + length], int(co), int(ci), int(kernel)).astype(np.float64)
    mult = metadata[moff + co:moff + 2 * co].astype(np.float64)
    shift = metadata[moff + 2 * co:moff + 3 * co].astype(np.float64)
    scale = mult / np.exp2(shift)
    float_weight = int8 * scale[:, None, None, None]
    key = f"layers.{index}.weight"
    state[key] = torch.from_numpy(float_weight.astype(np.float32))
    counts[int(index)] = float(scale.mean())
torch.save({"state_dict": state, "options": {"colorMode": "GRAY"}, "epoch": 0,
            "source": "MILK-W8A8-20261017@38285564"}, OUT)
print("warm-start layers:", len(counts), "mean scales:", {k: round(v, 5) for k, v in list(counts.items())[:6]})
print("saved", OUT, OUT.stat().st_size)
