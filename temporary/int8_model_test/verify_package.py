"""Verify the delivered INT8 package and its integer golden outputs on the PC."""
import argparse
from io import BytesIO
import hashlib
import json
import math
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

parser = argparse.ArgumentParser()
parser.add_argument('package')
parser.add_argument('gray_candidate_package')
parser.add_argument('--output-dir', type=Path)
args = parser.parse_args()
torch.set_num_threads(4)

def requant(value, multiplier, shift):
    product = value.to(torch.int64) * multiplier
    magnitude = (product.abs() + (1 << (shift - 1))) >> shift
    return torch.where(product < 0, -magnitude, magnitude).clamp(-127, 127).to(torch.int8)

with zipfile.ZipFile(args.package) as archive:
    prefix = 'int8_w8a8/'
    def read(name):
        return archive.read(prefix + name)
    manifest = json.loads(read('SHA256.json'))
    for name, expected in manifest.items():
        assert hashlib.sha256(read(name)).hexdigest() == expected, name
    config = json.loads(read('model_config.json'))
    quant = json.loads(read('quantization.json'))
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / 'quantization.json').write_text(json.dumps(quant), encoding='utf-8')
        for name in manifest:
            if name.startswith('weights/'):
                target = args.output_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(read(name))
    assert quant['input_shape'] == [1, 224, 224]
    assert quant['zero_point'] == 0
    assert quant['output_shapes'] == [[33, 7, 7], [33, 14, 14]]
    assert config['num_classes'] == 6
    def tensor(name, dtype, shape):
        values = np.frombuffer(read(name), dtype=dtype).copy()
        assert values.size == math.prod(shape), name
        return torch.from_numpy(values.reshape(shape))
    activations = {'input': tensor('golden_patches_4/input_quantized.bin', 'i1', [1, 1, 224, 224])}
    if args.output_dir:
        (args.output_dir / 'input.bin').write_bytes(activations['input'].numpy().tobytes())
    with zipfile.ZipFile(args.gray_candidate_package) as candidate:
        names = candidate.namelist()
        source = json.loads(read('source_manifest.json'))
        for name, expected in source['weights_sha256'].items():
            matches = [n for n in names if n.endswith('/folded_weight_s1_gray224/' + name)]
            assert len(matches) == 1, name
            assert hashlib.sha256(candidate.read(matches[0])).hexdigest() == expected, name
        images = [n for n in names if n.endswith('/patches_4.jpg')]
        assert len(images) == 1
        image = Image.open(BytesIO(candidate.read(images[0]))).convert('L')
        original_size = image.size
        image = image.resize((224, 224), Image.Resampling.BICUBIC)
        input_quantized = np.floor(np.asarray(image, dtype=np.float64) * 127 / 255 + 0.5).astype('i1')
        assert np.array_equal(input_quantized, activations['input'].numpy().reshape(224, 224))
        print('PASS: folded-weight provenance and image preprocessing', original_size, 'to 224x224')
    total_weights = 0
    with torch.inference_mode():
        for node in quant['graph']:
            name = node['name']
            inputs = [activations[src] for src in node['src']]
            if node['op'] == 'conv':
                params = quant['layers'][name]
                shape = params['weight_shape']
                weights = tensor(params['weight_file'], 'i1', shape)
                biases = tensor(params['bias_file'], '<i4', [shape[0]])
                # FP64 carries these bounded integer sums exactly; no INT16 clipping.
                accumulator = F.conv2d(inputs[0].double(), weights.double(), biases.double(),
                                       stride=node['stride'], padding=node['k'] // 2)
                assert torch.equal(accumulator, accumulator.round()), name
                assert accumulator.abs().max() < 2**31, name
                def scaled(key, shift_key):
                    m = torch.tensor(params[key], dtype=torch.int64).reshape(1, -1, 1, 1)
                    s = torch.tensor(params[shift_key], dtype=torch.int64).reshape(1, -1, 1, 1)
                    return requant(accumulator, m, s)
                output = scaled('multiplier', 'shift')
                if node['act']:
                    output = torch.where(accumulator >= 0, output, scaled('negative_multiplier', 'negative_shift'))
                total_weights += math.prod(shape)
                print(name, 'weights', math.prod(shape), 'weight range', int(weights.min()), int(weights.max()),
                      'bias range', int(biases.min()), int(biases.max()), 'output', tuple(output.shape[1:]))
            elif node['op'] == 'slice':
                output = inputs[0][:, node['start']:]
            elif node['op'] == 'pool':
                output = torch.stack([inputs[0][:, :, r::2, c::2] for r in range(2) for c in range(2)]).amax(0)
            elif node['op'] == 'upsample':
                output = inputs[0].repeat_interleave(2, 2).repeat_interleave(2, 3)
            elif node['op'] == 'concat':
                branches = []
                for src, value in zip(node['src'], inputs):
                    ratio = quant['activation_scales'][src] / quant['activation_scales'][name]
                    if ratio != 1:
                        mantissa, exponent = math.frexp(ratio)
                        multiplier = math.floor(mantissa * 2**31 + 0.5)
                        shift = 31 - exponent
                        if multiplier == 2**31:
                            multiplier //= 2
                            shift -= 1
                        value = requant(value, multiplier, shift)
                    branches.append(value)
                output = torch.cat(branches, 1)
            else:
                raise ValueError(node['op'])
            activations[name] = output
            if args.output_dir:
                (args.output_dir / (name + '.bin')).write_bytes(output.numpy().tobytes())
    for name, shape in zip(('out0', 'out1'), quant['output_shapes']):
        expected = tensor('golden_patches_4/' + name + '_quantized.bin', 'i1', [1] + shape)
        assert torch.equal(activations[name], expected), name
    print('PASS: hash checks', len(manifest), 'weight bytes', total_weights,
          'and both INT8 golden heads match exactly; this is a PC test, not an FPGA test')
