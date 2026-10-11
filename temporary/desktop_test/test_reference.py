import math
import struct
import sys
from pathlib import Path

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "camera/desktop"))
from postprocess import ANCHORS, CLASSES, detect

here = Path(__file__).resolve().parent
folder = sorted((here / "build/saved").glob("frame_*"))[-1]
raw = [(folder / f"out{kind}.bin").read_bytes() for kind in (0, 1)]
reference = []
for buffer, size, anchors in zip(raw, (13, 26), ANCHORS):
    values = struct.unpack(f"<{len(buffer)//2}h", buffer)
    for anchor in range(3):
        for row in range(size):
            for column in range(size):
                prediction = [values[(anchor * 25 + channel) * size * size + row * size + column] / 512
                              for channel in range(25)]
                class_id = max(range(20), key=lambda index: prediction[5 + index])
                score = 1 / (1 + math.exp(-prediction[4])) / (1 + math.exp(-prediction[5 + class_id]))
                if score < .05:
                    continue
                x = (1 / (1 + math.exp(-prediction[0])) + column) * 416 / size
                y = (1 / (1 + math.exp(-prediction[1])) + row) * 416 / size
                width = math.exp(prediction[2]) * anchors[anchor][0] * 416 / size
                height = math.exp(prediction[3]) * anchors[anchor][1] * 416 / size
                reference.append((class_id, score, [x-width/2, y-height/2, x+width/2, y+height/2]))


def overlap(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (area_a + area_b - intersection)


kept = []
for class_id in sorted(set(item[0] for item in reference)):
    pending = sorted((item for item in reference if item[0] == class_id), key=lambda item: -item[1])
    while pending:
        best = pending.pop(0)
        kept.append(best)
        pending = [item for item in pending if overlap(best[2], item[2]) <= .3]
kept.sort(key=lambda item: -item[1])
actual = detect(*raw, confidence=.05)
assert len(actual) == len(kept)
for result, expected in zip(actual, kept):
    assert result["class_name"] == CLASSES[expected[0]]
    assert abs(result["score"] - expected[1]) < 1e-12
    np.testing.assert_allclose(result["box"], np.clip(expected[2], 0, 416), atol=1e-10)
print(f"PASS: independent scalar author-formula comparison, {len(reference)} candidates -> {len(kept)} detections")
