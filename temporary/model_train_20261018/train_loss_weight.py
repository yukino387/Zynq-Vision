"""Retrain milk two-class with a stronger objectness positive weight."""
import json, math, random, sys
from pathlib import Path
import torch
from torch.nn import functional as F
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
sys.path.insert(0, str(ROOT / "camera/training"))
sys.path.insert(0, str(ROOT / "temporary/model_train_20261018"))
import train_last
from data import Samples
from detection import ANCHORS
from pl_model import FixedGraph

START = ROOT / "temporary/model_train_20261018/milk_run4/checkpoint.pt"
P, N = 8.0, 0.05  # positive / negative objectness weights

def loss_weighted(outputs, boxes):
    total = outputs[0].new_tensor(0.)
    targets = []
    for out in outputs:
        b, _, size, _ = out.shape
        targets.append((out.reshape(b, 3, 11, size, size).permute(0, 1, 3, 4, 2), torch.zeros((b, 3, size, size, 11))))
    anchors = [(h, a, w / size, height / size) for h, size in enumerate((7, 14)) for a, (w, height) in enumerate(ANCHORS[h])]
    for batch, labels in enumerate(boxes):
        for cls, x1, y1, x2, y2 in labels.tolist():
            x, y, w, height = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
            ranked = sorted(anchors, reverse=True, key=lambda a: min(w, a[2]) * min(height, a[3]) / (w * height + a[2] * a[3] - min(w, a[2]) * min(height, a[3])))
            best = None
            for anchor in ranked:
                h, a, _, _ = anchor
                target = targets[h][1]; size = target.shape[2]
                row, col = min(int(y * size), size - 1), min(int(x * size), size - 1)
                if not target[batch, a, row, col, 4]:
                    best = anchor; break
            if best is None: raise ValueError('More overlapping boxes than available detector anchors')
            h, a, aw, ah = best; target = targets[h][1]; size = target.shape[2]
            col, row = min(int(x * size), size - 1), min(int(y * size), size - 1)
            target[batch, a, row, col, :5] = target.new_tensor([x * size - col, y * size - row, math.log(w / aw), math.log(height / ah), 1.])
            target[batch, a, row, col, 5 + int(cls)] = 1.
    for logits, target in targets:
        has_positive = bool(target[..., 4].any())
        target = target.to(logits.device, non_blocking=True)
        positive = target[..., 4].bool()
        total = total + F.binary_cross_entropy_with_logits(logits[..., 4], target[..., 4], reduction='none').mul(torch.where(positive, P, N)).mean()
        if has_positive:
            pred, truth = logits[positive], target[positive]
            total = total + 5 * F.binary_cross_entropy_with_logits(pred[:, :2], truth[:, :2]) + 2 * F.smooth_l1_loss(pred[:, 2:4], truth[:, 2:4]) + F.binary_cross_entropy_with_logits(pred[:, 5:], truth[:, 5:])
    return total

class CachedAugSamples(Samples):
    def __init__(self, items, mode):
        super().__init__(items, mode)
        self.augment = bool(items) and all(i.get("split") == "train" for i in items)
        self.cache = {}
    def __getitem__(self, index):
        if index not in self.cache: self.cache[index] = super().__getitem__(index)
        x, boxes = self.cache[index]; x, boxes = x.clone(), boxes.clone()
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
        print(f"warm-start from {START.name} epoch {ckpt.get('epoch')}, P={P} N={N}", flush=True)

train_last.Samples = CachedAugSamples
train_last.FixedGraph = WarmGraph
train_last.loss = loss_weighted
spec_path = Path(sys.argv[1]); out = Path(sys.argv[2])
spec = json.loads(spec_path.read_text(encoding="utf-8"))
spec["options"]["epochs"] = int(sys.argv[3]) if len(sys.argv) > 3 else 200
spec["version"] = "INT8-MILK-STRAW-20261018-F"
Path(ROOT / "temporary/model_train_20261018/milk_spec_weight.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
train_last.run(spec, out)
