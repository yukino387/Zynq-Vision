"""Augmented training initialized from the board's previous GRAY model."""
import json, random, sys
from pathlib import Path
import torch
TRAIN_DIR = Path(r"C:/00_workplace/fpga/cnn_accelerator/camera/training")
sys.path.insert(0, str(TRAIN_DIR))
import train
from data import Samples
from pl_model import FixedGraph

WARM = Path(r"C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018/warm.pt")

class AugSamples(Samples):
    def __init__(self, items, mode):
        super().__init__(items, mode)
        self.augment = bool(items) and all(item.get("split") == "train" for item in items)
    def __getitem__(self, index):
        x, boxes = super().__getitem__(index)
        if not self.augment or not len(boxes): return x, boxes
        boxes = boxes.clone()
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
        state = torch.load(WARM, weights_only=True, map_location="cpu")["state_dict"]
        missing, unexpected = self.load_state_dict(state, strict=False)
        print(f"warm-start loaded: {len(state)} tensors, missing {len(missing)}, unexpected {len(unexpected)}", flush=True)

train.Samples = AugSamples
train.FixedGraph = WarmGraph
spec = Path(sys.argv[1]); out = Path(sys.argv[2])
train.run(json.loads(spec.read_text(encoding="utf-8")), out)
