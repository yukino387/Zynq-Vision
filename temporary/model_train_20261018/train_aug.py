"""Run camera/training/train.py with on-the-fly augmentation for the train split only."""
import random, sys
from pathlib import Path
import torch

TRAIN_DIR = Path(r"C:/00_workplace/fpga/cnn_accelerator/camera/training")
sys.path.insert(0, str(TRAIN_DIR))
import train
from data import Samples


class AugSamples(Samples):
    def __init__(self, items, mode):
        super().__init__(items, mode)
        self.augment = bool(items) and all(item.get("split") == "train" for item in items)

    def __getitem__(self, index):
        x, boxes = super().__getitem__(index)
        if not self.augment or not len(boxes):
            return x, boxes
        boxes = boxes.clone()
        if random.random() < 0.5:                       # horizontal flip
            x = x.flip(-1)
            boxes[:, 1], boxes[:, 3] = 1 - boxes[:, 3], 1 - boxes[:, 1]
        if random.random() < 0.25:                      # vertical flip
            x = x.flip(-2)
            boxes[:, 2], boxes[:, 4] = 1 - boxes[:, 4], 1 - boxes[:, 2]
        if random.random() < 0.8:                       # brightness / contrast
            x = torch.clamp(x * random.uniform(0.75, 1.25) + random.uniform(-0.12, 0.12), 0, 1)
        if random.random() < 0.4:                       # gamma
            x = torch.clamp(x, 1e-4, 1) ** random.uniform(0.7, 1.4)
        if random.random() < 0.3:                       # sensor-like noise
            x = torch.clamp(x + torch.randn_like(x) * 0.02, 0, 1)
        return x, boxes


train.Samples = AugSamples
spec = Path(sys.argv[1]); out = Path(sys.argv[2])
train.run(__import__("json").loads(spec.read_text(encoding="utf-8")), out)
