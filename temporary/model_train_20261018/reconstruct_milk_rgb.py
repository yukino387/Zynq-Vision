"""Reconstruct the MILK-RGB INT8 package as FP32 by deriving per-layer scales."""
import json, sqlite3, sys
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
hidden_ws = []
for index, (_, _, woff, moff, ci, co, _, _, kernel, act) in enumerate(model.commands):
    if kernel in (1, 3) and index != 0 and index not in HEADS:
        mult = metadata[moff + co:moff + 2 * co].astype(np.float64)
        shift = metadata[moff + 2 * co:moff + 3 * co].astype(np.float64)
        hidden_ws.extend((mult / np.exp2(shift)).tolist())
hidden_ws = np.array(hidden_ws)
print("hidden ws median/mean/min/max", np.round(np.median(hidden_ws), 6), np.round(hidden_ws.mean(), 6), np.round(hidden_ws.min(), 6), np.round(hidden_ws.max(), 6))
# first-layer and head ratios
for index in (0, *HEADS):
    _, _, woff, moff, ci, co, _, _, kernel, act = model.commands[index]
    mult = metadata[moff + co:moff + 2 * co].astype(np.float64)
    shift = metadata[moff + 2 * co:moff + 3 * co].astype(np.float64)
    r = mult / np.exp2(shift)
    print("layer", index, "ratio median", round(float(np.median(r)), 6), "min", round(float(r.min()), 6), "max", round(float(r.max()), 6))
ws_med = float(np.median(hidden_ws))
_, _, _, m0, _, c0, _, _, _, _ = model.commands[0]
r0 = metadata[m0 + c0:m0 + 2 * c0] / np.exp2(metadata[m0 + 2 * c0:m0 + 3 * c0])
_, _, _, mh, _, ch, _, _, _, _ = model.commands[HEADS[0]]
rh = metadata[mh + ch:mh + 2 * ch] / np.exp2(metadata[mh + 2 * ch:mh + 3 * ch])
print("hidden_scale from first", (1 / 127) * ws_med / np.median(r0))
print("hidden_scale from head ", np.median(rh) * OUTPUT_SCALES[0] / ws_med)
