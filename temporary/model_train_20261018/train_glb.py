import json, random, sys
from pathlib import Path
import torch
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
sys.path.insert(0, str(ROOT / "temporary/model_train_20261018"))
import train_last
from data import Samples
from pl_model import FixedGraph

START = ROOT / "temporary/model_train_20261018/milk_run4/checkpoint.pt"

class CachedAugSamples(Samples):
    def __init__(self, items, mode):
        super().__init__(items, mode)
        self.augment = bool(items) and all(i.get("split") == "train" for i in items)
        self.cache = {}
    def __getitem__(self, index):
        if index not in self.cache:
            self.cache[index] = super().__getitem__(index)
        x, boxes = self.cache[index]
        x, boxes = x.clone(), boxes.clone()
        if not self.augment or not len(boxes): return x, boxes
        if random.random() < 0.5:
            x = x.flip(-1); boxes[:, 1], boxes[:, 3] = 1 - boxes[:, 3], 1 - boxes[:, 1]
        if random.random() < 0.25:
            x = x.flip(-2); boxes[:, 2], boxes[:, 4] = 1 - boxes[:, 4], 1 - boxes[:, 2]
        if random.random() < 0.8:
            x = torch.clamp(x * random.uniform(0.75, 1.25) + random.uniform(-0.12, 0.12), 0, 1)
        if random.random() < 0.4:
            x = torch.clamp(x, 1e-4, 1) ** random.uniform(0.7, 1.4)
        if random.random() < 0.3:
            x = torch.clamp(x + torch.randn_like(x) * 0.02, 0, 1)
        return x, boxes

class WarmGraph(FixedGraph):
    def __init__(self, channels):
        super().__init__(channels)
        ckpt = torch.load(START, weights_only=True, map_location="cpu")
        self.load_state_dict(ckpt["state_dict"])
        print(f"warm-start from epoch {ckpt.get('epoch')}", flush=True)

train_last.Samples = CachedAugSamples
train_last.FixedGraph = WarmGraph

spec_path = Path(sys.argv[1]); out = Path(sys.argv[2])
spec = json.loads(spec_path.read_text(encoding="utf-8"))
spec["options"]["epochs"] = int(sys.argv[3]) if len(sys.argv) > 3 else 300
spec["version"] = "INT8-MILK-STRAW-GLB-20261018"
Path(ROOT / "temporary/model_train_20261018/milk_spec_last.json").write_text(
    json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
train_last.run(spec, out)
