"""Warm-start hidden layers of FixedGraph(3) from the existing MILK-RGB INT8 package."""
import sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from pl_model import FixedGraph, HEADS, unpack_weights
PKG = ROOT / "data/storage/models/65ce8fc8-29a6-4ff9-b85e-53e95c3c636c"  # MILK-RGB-20261017
OUT = ROOT / "temporary/model_train_20261018/warm_rgb.pt"
WEIGHT_BYTES = 6350208
pkg = PKG.read_bytes(); weights = pkg[128:128 + WEIGHT_BYTES]
metadata = np.frombuffer(pkg[128 + WEIGHT_BYTES:], dtype="<i4")
model = FixedGraph(3); state = model.state_dict(); counts = {}
for index, (_, _, woff, moff, ci, co, _, _, kernel, act) in enumerate(model.commands):
    if kernel not in (1, 3) or index == 0 or index in HEADS:
        continue
    length = ((co + 47) // 48 * 48) * ((ci + 7) // 8 * 8) * kernel**2
    int8 = unpack_weights(weights[woff:woff + length], int(co), int(ci), int(kernel)).astype(np.float64)
    scale = metadata[moff + co:moff + 2 * co].astype(np.float64) / np.exp2(metadata[moff + 2 * co:moff + 3 * co].astype(np.float64))
    state[f"layers.{index}.weight"] = torch.from_numpy((int8 * scale[:, None, None, None]).astype(np.float32))
    counts[int(index)] = float(scale.mean())
torch.save({"state_dict": state, "options": {"colorMode": "RGB"}, "epoch": 0,
            "source": "MILK-RGB-20261017@65ce8fc8"}, OUT)
print("warm layers", len(counts), "saved", OUT, OUT.stat().st_size)
