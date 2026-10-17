"""The anchor order and logits match packages/device-protocol/src/postprocess.ts."""
import math
import numpy as np
import torch
from torch.nn import functional as F

ANCHORS = [
    [(1.3629538461538462, 1.3798076923076923), (2.2716615384615384, 2.843723076923077), (5.788461538461538, 5.367815384615384)],
    [(.7740384615384615, .9086538461538461), (1.2451923076923077, 1.9519230769230769), (2.7259615384615383, 2.7596153846153846)],
]


def loss(outputs, boxes):
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
                target = targets[h][1]
                size = target.shape[2]
                row, col = min(int(y * size), size - 1), min(int(x * size), size - 1)
                if not target[batch, a, row, col, 4]:
                    best = anchor
                    break
            if best is None:
                raise ValueError('More overlapping boxes than available detector anchors')
            h, a, aw, ah = best
            target = targets[h][1]
            size = target.shape[2]
            col, row = min(int(x * size), size - 1), min(int(y * size), size - 1)
            target[batch, a, row, col, :5] = target.new_tensor([x * size - col, y * size - row, math.log(w / aw), math.log(height / ah), 1.])
            target[batch, a, row, col, 5 + int(cls)] = 1.
    for logits, target in targets:
        has_positive = bool(target[..., 4].any())
        target = target.to(logits.device, non_blocking=True)
        positive = target[..., 4].bool()
        total = total + F.binary_cross_entropy_with_logits(logits[..., 4], target[..., 4], reduction='none').mul(torch.where(positive, 1., .05)).mean()
        if has_positive:
            pred, truth = logits[positive], target[positive]
            total = total + 5 * F.binary_cross_entropy_with_logits(pred[:, :2], truth[:, :2]) + 2 * F.smooth_l1_loss(pred[:, 2:4], truth[:, 2:4]) + F.binary_cross_entropy_with_logits(pred[:, 5:], truth[:, 5:])
    return total


def iou(a, b):
    lo, hi = np.maximum(a[:2], b[:2]), np.minimum(a[2:], b[2:])
    intersection = np.maximum(hi - lo, 0).prod()
    union = np.maximum(a[2:] - a[:2], 0).prod() + np.maximum(b[2:] - b[:2], 0).prod() - intersection
    return intersection / union if union > 0 else 0.


def decode(outputs, threshold=.05):
    candidates = []
    for h, raw in enumerate(outputs):
        size = raw.shape[-1]
        logits = raw.numpy().reshape(3, 11, size, size).transpose(0, 2, 3, 1)
        sig = 1 / (1 + np.exp(-np.clip(logits, -50, 50)))
        for a, row, col in np.argwhere(sig[..., 4] * sig[..., 5:].max(-1) >= threshold):
            cls = int(logits[a, row, col, 5:].argmax())
            score = float(sig[a, row, col, 4] * sig[a, row, col, cls + 5])
            x, y = (sig[a, row, col, 0] + col) / size, (sig[a, row, col, 1] + row) / size
            w, height = np.exp(np.clip(logits[a, row, col, 2:4], -30, 30)) * np.array(ANCHORS[h][a]) / size
            candidates.append((score, cls, np.array([x - w / 2, y - height / 2, x + w / 2, y + height / 2])))
    kept = []
    for candidate in sorted(candidates, key=lambda b: -b[0]):
        if not any(k[1] == candidate[1] and iou(k[2], candidate[2]) > .45 for k in kept):
            kept.append(candidate)
    return [(score, cls, box.clip(0, 1)) for score, cls, box in kept]


def metrics(predictions, labels):
    aps, true_positive, false_positive, count = [], 0, 0, 0
    for cls in range(6):
        truths = {i: [row[1:] for row in label.numpy() if int(row[0]) == cls] for i, label in enumerate(labels)}
        total = sum(map(len, truths.values()))
        count += total
        ranked = sorted([(score, i, box) for i, pred in enumerate(predictions) for score, category, box in pred if category == cls], reverse=True, key=lambda p: p[0])
        matched, tp, fp = set(), [], []
        for score, image, box in ranked:
            overlaps = [iou(box, truth) if (image, j) not in matched else -1 for j, truth in enumerate(truths[image])]
            match = int(np.argmax(overlaps)) if overlaps else -1
            hit = match >= 0 and overlaps[match] >= .5
            if hit:
                matched.add((image, match))
            tp.append(int(hit)); fp.append(int(not hit))
            if score >= .35:
                true_positive += int(hit); false_positive += int(not hit)
        if total:
            recall = np.cumsum(tp) / total
            precision = np.cumsum(tp) / np.maximum(np.cumsum(tp) + np.cumsum(fp), 1)
            aps.append(float(np.mean([precision[recall >= r].max() if np.any(recall >= r) else 0. for r in np.linspace(0, 1, 101)])))
    return {'mAP50': float(np.mean(aps)) if aps else None, 'precision': true_positive / max(true_positive + false_positive, 1), 'recall': true_positive / count if count else None, 'validationImages': len(labels), 'groundTruthBoxes': count, 'evaluation': 'INT8 reference, IoU=0.50, 101-point AP, precision/recall confidence=0.35'}
