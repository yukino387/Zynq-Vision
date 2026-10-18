"""Identify which stored package produced a sample's TENSOR_OUT assets."""
import sqlite3, sys
from pathlib import Path
import numpy as np, torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
from pl_model import FixedGraph, integer_forward

c = sqlite3.connect(ROOT / "data/app.db"); c.row_factory = sqlite3.Row
sid = "cmvcti2ud00heueqg12hp0qy6"
assets = {r["kind"]: ROOT / "data/storage" / r["storageKey"] for r in c.execute(
    "select kind,storageKey from Asset where sampleId=? and deletedAt is null", (sid,))}
x = torch.frombuffer(bytearray(assets["MODEL_INPUT"].read_bytes()), dtype=torch.int8).reshape(1, 1, 224, 224)
print("model input range", int(x.min()), int(x.max()))
out0 = np.frombuffer(assets["TENSOR_OUT0"].read_bytes(), dtype=np.int8)
out1 = np.frombuffer(assets["TENSOR_OUT1"].read_bytes(), dtype=np.int8)
for model in c.execute("""select m.id,m.version,a.assetId,ast.storageKey from Model m
    join ModelArtifact a on a.modelId=m.id join Asset ast on ast.id=a.assetId
    where a.kind='WEIGHTS' and ast.size=6416360"""):
    pkg = (ROOT / "data/storage" / model["storageKey"]).read_bytes()
    weights, metadata = pkg[128:128 + 6350208], pkg[128 + 6350208:]
    try:
        out = integer_forward(FixedGraph(1), x, weights, metadata)
        a = out[0][0].to(torch.int8).numpy().tobytes(); b = out[1][0].to(torch.int8).numpy().tobytes()
        print(model["version"], model["storageKey"], "out0", a == out0.tobytes(), "out1", b == out1.tobytes(),
              "maxdiff0", int(np.abs(np.frombuffer(a, np.int8).astype(int) - out0.astype(int)).max()))
    except Exception as e:
        print(model["version"], "ERR", e)
