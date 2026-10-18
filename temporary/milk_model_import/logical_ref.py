"""Logical (no memory layout) integer reference for the delivery package, checked against its golden."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

PACKAGE = Path(sys.argv[1] if len(sys.argv) > 1 else
               r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_int8_20261017/给队长_牛奶换型包_int8_20261017/牛奶_int8_w8a8')


def coefficients(ratio):
    mantissa, exponent = math.frexp(ratio)
    multiplier = math.floor(mantissa * 2**31 + .5)
    shift = 31 - exponent
    if multiplier == 2**31:
        multiplier //= 2
        shift -= 1
    return multiplier, shift


def requant(value, multiplier, shift):
    product = np.asarray(value, dtype=np.int64) * np.int64(multiplier)
    magnitude = np.abs(product)
    rounded = (magnitude + (np.int64(1) << np.int64(shift - 1))) >> np.int64(shift)
    return np.clip(np.where(product < 0, -rounded, rounded), -127, 127)


def main():
    quant = json.loads((PACKAGE / 'quantization.json').read_text(encoding='utf-8'))
    scales = quant['activation_scales']
    layers = quant['layers']
    values = {}
    image = np.fromfile(PACKAGE / 'golden_patches_4/input_quantized.bin', dtype=np.int8)
    values['input'] = image.reshape(1, 224, 224).astype(np.int64)
    for node in quant['graph']:
        name, op = node['name'], node['op']
        if op == 'conv':
            layer = layers[name]
            x = torch.from_numpy(values[node['src'][0]]).double()
            shape = tuple(layer['weight_shape'])
            weight = torch.from_numpy(np.fromfile(PACKAGE / layer['weight_file'], dtype='i1').reshape(shape)).double()
            bias = torch.from_numpy(np.fromfile(PACKAGE / layer['bias_file'], dtype='<i4')).to(torch.int64)
            k = int(node['k'])
            acc = F.conv2d(x, weight, bias.double(), stride=int(node['stride']), padding=k // 2)
            if not torch.equal(acc, acc.round()):
                raise ValueError(f'non-integer accumulator at {name}')
            acc = acc.round().to(torch.int64).numpy()
            pos = requant(acc, np.array(layer['multiplier'])[:, None, None], np.array(layer['shift'])[:, None, None])
            neg = requant(acc, np.array(layer['negative_multiplier'])[:, None, None],
                          np.array(layer['negative_shift'])[:, None, None])
            values[name] = np.where(acc < 0, neg, pos) if node['act'] else pos
        elif op == 'slice':
            values[name] = values[node['src'][0]][int(node['start']):]
        elif op == 'concat':
            target = scales[name]
            parts = []
            for src in node['src']:
                if scales[src] == target:
                    parts.append(values[src])
                else:
                    multiplier, shift = coefficients(scales[src] / target)
                    parts.append(requant(values[src], multiplier, shift))
            values[name] = np.concatenate(parts, axis=0)
        elif op == 'pool':
            x = values[node['src'][0]]
            c, h, w = x.shape
            values[name] = x.reshape(c, h // 2, 2, w // 2, 2).max(axis=(2, 4))
        elif op == 'upsample':
            x = values[node['src'][0]]
            values[name] = x.repeat(2, axis=1).repeat(2, axis=2)
        else:
            raise ValueError(op)
    np.savez(r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_model_import/logical_intermediates.npz',
             **{name: tensor.astype(np.int8) for name, tensor in values.items()})
    out0, out1 = values['out0'], values['out1']
    g0 = np.fromfile(PACKAGE / 'golden_patches_4/out0_quantized.bin', dtype=np.int8)
    g1 = np.fromfile(PACKAGE / 'golden_patches_4/out1_quantized.bin', dtype=np.int8)
    d0 = out0.reshape(-1).astype(np.int32) - g0.astype(np.int32)
    d1 = out1.reshape(-1).astype(np.int32) - g1.astype(np.int32)
    report = {
        'out0_equal': bool(np.array_equal(out0.reshape(-1), g0)),
        'out1_equal': bool(np.array_equal(out1.reshape(-1), g1)),
        'out0_max_abs_diff': int(np.abs(d0).max()),
        'out1_max_abs_diff': int(np.abs(d1).max()),
        'out0_mismatch': int((d0 != 0).sum()),
        'out1_mismatch': int((d1 != 0).sum()),
    }
    print(json.dumps(report, indent=2))
    np.save(r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_model_import/logical_out0.npy', out0.astype(np.int8))
    np.save(r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_model_import/logical_out1.npy', out1.astype(np.int8))
    return 0 if report['out0_equal'] and report['out1_equal'] else 1


if __name__ == '__main__':
    sys.exit(main())
