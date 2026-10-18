"""Bit-exact integer reference for the board layout; compares with the delivery golden patches."""
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(r'C:/00_workplace/fpga/cnn_accelerator')
COMMANDS = np.array(json.loads((ROOT / 'camera/training/graph.json').read_text(encoding='utf-8'))['commands'],
                    dtype='<i4')
FEATURE_BYTES = 3012640
OUT0_OFFSET, OUT1_OFFSET = 2910208, 3005248

BOARD = Path(sys.argv[1] if len(sys.argv) > 1 else
             r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_model_import/board_model_20261017')
PACKAGE = Path(sys.argv[2] if len(sys.argv) > 2 else
               r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_int8_20261017/给队长_牛奶换型包_int8_20261017/牛奶_int8_w8a8')

LEVELS = {7: 0, 14: 1, 28: 2, 56: 3, 112: 4, 224: 5}


def row_pitch(size):
    return 8 << LEVELS[size]


def plane_size(size):
    return size * row_pitch(size)


def get_planes(features, offset, channels, size):
    pitch = row_pitch(size)
    block = np.frombuffer(features[offset:offset + channels * plane_size(size)], dtype=np.int8)
    return block.reshape(channels, size, pitch)[:, :, :size].astype(np.int64).copy()


def put_planes(features, offset, size, values):
    channels = values.shape[0]
    pitch = row_pitch(size)
    block = np.zeros((channels, size, pitch), dtype=np.int8)
    block[:, :, :size] = values.astype(np.int8)
    features[offset:offset + channels * plane_size(size)] = block.tobytes()


def unpack_weights(data, co, ci, k):
    return np.frombuffer(data, dtype='i1').reshape(-1, (ci + 7) // 8, 4, 12, 8, k, k) \
        .transpose(0, 3, 2, 1, 4, 5, 6).reshape(-1, (ci + 7) // 8 * 8, k, k)[:co, :ci].copy()


def requant(value, multiplier, shift):
    product = np.asarray(value, dtype=np.int64) * np.int64(multiplier)
    magnitude = np.abs(product)
    rounded = (magnitude + (np.int64(1) << np.int64(shift - 1))) >> np.int64(shift)
    result = np.where(product < 0, -rounded, rounded)
    return np.clip(result, -127, 127)


def run(weights, metadata, image):
    words = np.frombuffer(metadata, dtype='<i4')
    status = {}
    features = bytearray(FEATURE_BYTES)
    put_planes(features, 0, 224, image.reshape(1, 224, 224).astype(np.int64))
    stats = []
    for index, (src, dst, woff, moff, ci, co, size, stride, kernel, act) in enumerate(COMMANDS):
        if kernel in (1, 3):
            length = ((co + 47) // 48 * 48) * ((ci + 7) // 8 * 8) * kernel * kernel
            weight = torch.from_numpy(unpack_weights(weights[woff:woff + length], co, ci, kernel)).double()
            values = torch.from_numpy(get_planes(features, src, ci, size)).double()
            params = torch.from_numpy(words[moff:moff + 5 * co].reshape(5, co)).to(torch.int64)
            accumulator = F.conv2d(values, weight, params[0].double(), stride=int(stride),
                                   padding=int(kernel // 2))
            check = accumulator.abs().max().item()
            if not torch.equal(accumulator, accumulator.round()):
                raise ValueError(f'non-integer accumulator at command {index}')
            acc = accumulator.round().to(torch.int64).numpy()
            pos = requant(acc, params[1].numpy()[:, None, None], params[2].numpy()[:, None, None])
            neg = requant(acc, params[3].numpy()[:, None, None], params[4].numpy()[:, None, None])
            out = np.where(acc < 0, neg, pos) if act else pos
            out_size = size // stride if stride == 2 else size
            put_planes(features, dst, out_size, out)
            status.setdefault('layers', {})[str(index)] = out.copy()
            stats.append({'index': index, 'acc_max': check, 'out_size': out_size})
        elif kernel == 2:
            values = get_planes(features, src, ci, size).reshape(ci, size // 2, 2, size // 2, 2).max(axis=(2, 4))
            put_planes(features, dst, size // 2, values)
            stats.append({'index': index, 'pool': ci})
        elif kernel == 0:
            values = get_planes(features, src, ci, size).repeat(2, axis=1).repeat(2, axis=2)
            put_planes(features, dst, size * 2, values)
            stats.append({'index': index, 'upsample': ci})
        elif kernel == 5:
            values = get_planes(features, src, ci, size)
            out = requant(values, int(words[moff]), int(words[moff + 1]))
            put_planes(features, dst, size, out)
            stats.append({'index': index, 'requant': ci})
    out0 = get_planes(features, OUT0_OFFSET, 33, 7)
    out1 = get_planes(features, OUT1_OFFSET, 33, 14)
    return out0.astype(np.int8), out1.astype(np.int8), stats, status['layers']


def sigmoid(value):
    return 1.0 / (1.0 + np.exp(-value))


def decode(raw, size, scale, anchors, threshold=0.5, iou=0.3):
    """Python port of camera/winui/Postprocess.cs."""
    raw = raw.reshape(-1)
    detections = []
    for anchor in range(3):
        for cell in range(size * size):
            def value(channel):
                return int(np.int8(raw[(anchor * 11 + channel) * size * size + cell])) * scale
            obj = sigmoid(value(4))
            if obj < threshold:
                continue
            best_class = max(range(6), key=lambda c: value(5 + c))
            score = obj * sigmoid(value(5 + best_class))
            if score < threshold:
                continue
            x = (sigmoid(value(0)) + cell % size) * 416 / size
            y = (sigmoid(value(1)) + cell // size) * 416 / size
            w = np.exp(value(2)) * anchors[anchor * 2] * 416 / size
            h = np.exp(value(3)) * anchors[anchor * 2 + 1] * 416 / size
            detections.append({'class': best_class, 'score': score,
                               'box': (x - w / 2, y - h / 2, x + w / 2, y + h / 2)})
    kept = []
    for class_id in {d['class'] for d in detections}:
        remaining = sorted([d for d in detections if d['class'] == class_id],
                           key=lambda d: -d['score'])
        while remaining:
            best = remaining.pop(0)
            kept.append(best)
            remaining = [d for d in remaining if _overlap(best['box'], d['box']) <= iou]
    return sorted(kept, key=lambda d: -d['score'])


def _overlap(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0


HEAD_SCALES = (0.11581249687615341, 0.15977688286248154)
ANCHORS = ([1.3629538461538462, 1.3798076923076923, 2.2716615384615384, 2.843723076923077,
            5.788461538461538, 5.367815384615384],
           [0.7740384615384615, 0.9086538461538461, 1.2451923076923077,
            1.9519230769230769, 2.7259615384615383, 2.7596153846153846])


def main():
    weights = (BOARD / 'weights.bin').read_bytes()
    metadata = (BOARD / 'metadata.bin').read_bytes()
    quant = json.loads((PACKAGE / 'quantization.json').read_text(encoding='utf-8'))
    golden = PACKAGE / 'golden_patches_4'
    image = np.fromfile(golden / 'input_quantized.bin', dtype=np.int8)
    assert image.size == 224 * 224
    out0, out1, stats, layers = run(weights, metadata, image)
    np.savez(r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_model_import/board_intermediates.npz', **layers)
    g0 = np.fromfile(golden / 'out0_quantized.bin', dtype=np.int8).reshape(33, 7, 7)
    g1 = np.fromfile(golden / 'out1_quantized.bin', dtype=np.int8).reshape(33, 14, 14)

    real0 = out0.astype(np.float64) * HEAD_SCALES[0]
    real1 = out1.astype(np.float64) * HEAD_SCALES[1]
    gold0 = g0.astype(np.float64) * quant['activation_scales']['out0']
    gold1 = g1.astype(np.float64) * quant['activation_scales']['out1']
    board_detections = decode(out0, 7, HEAD_SCALES[0], ANCHORS[0]) + decode(out1, 14, HEAD_SCALES[1], ANCHORS[1])
    golden_detections = (decode(g0, 7, quant['activation_scales']['out0'], ANCHORS[0]) +
                         decode(g1, 14, quant['activation_scales']['out1'], ANCHORS[1]))
    report = {
        'out0_max_real_diff': float(np.abs(real0 - gold0).max()),
        'out1_max_real_diff': float(np.abs(real1 - gold1).max()),
        'out0_mean_real_diff': float(np.abs(real0 - gold0).mean()),
        'out1_mean_real_diff': float(np.abs(real1 - gold1).mean()),
        'board_detections': len(board_detections),
        'golden_detections': len(golden_detections),
        'board_top_score': board_detections[0]['score'] if board_detections else 0.0,
        'golden_top_score': golden_detections[0]['score'] if golden_detections else 0.0,
        'max_score_diff': float(max(
            [abs(a['score'] - b['score']) for a, b in zip(board_detections, golden_detections)] or [0.0])),
        'max_box_diff': float(max(
            [abs(x - y) for a, b in zip(board_detections, golden_detections)
             for x, y in zip(a['box'], b['box'])] or [0.0])),
    }
    print(json.dumps(report, indent=2))
    return 0 if report['max_score_diff'] < 0.02 and report['max_box_diff'] < 2.0 else 1


if __name__ == '__main__':
    sys.exit(main())
