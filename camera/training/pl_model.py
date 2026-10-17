"""Trainable fixed graph and the byte layout consumed by hardware/hls/src/."""
import hashlib
import json
import math
import struct
import zlib
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[2]
GRAPH = json.loads((Path(__file__).parent / 'graph.json').read_text())
COMMANDS = np.array(GRAPH['commands'], dtype='<i4')
WEIGHT_BYTES = 6350208
METADATA_WORDS = 16506
OUTPUT_SCALES = [0.11581249687615341, 0.15977688286248154]
CLASSES = ['龟裂', '夹杂', '斑块', '麻点', '轧入氧化皮', '划痕']
HEADS = (26, 32)


def plane(size):
    return size * (size * 8 // 7)


def commands_for(channels):
    if channels not in (1, 3):
        raise ValueError('Only GRAY (1) and RGB (3) channels are supported')
    commands = COMMANDS.copy()
    commands[0, 4] = channels
    return commands


def pack_weights(weight):
    """[M/48,N/8,4,12,8,K,K], zero padded on both channel axes."""
    co, ci, k, _ = weight.shape
    padded = np.zeros(((co + 47) // 48 * 48, (ci + 7) // 8 * 8, k, k), dtype='i1')
    padded[:co, :ci] = weight
    return padded.reshape(-1, 12, 4, padded.shape[1] // 8, 8, k, k).transpose(0, 3, 2, 1, 4, 5, 6).tobytes()


def unpack_weights(data, co, ci, k):
    return np.frombuffer(data, dtype='i1').reshape(-1, (ci + 7) // 8, 4, 12, 8, k, k).transpose(0, 3, 2, 1, 4, 5, 6).reshape(-1, (ci + 7) // 8 * 8, k, k)[:co, :ci].copy()


def coefficients(ratio):
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError('Invalid requantization ratio')
    mantissa, exponent = math.frexp(ratio)
    multiplier = math.floor(mantissa * 2**31 + .5)
    shift = 31 - exponent
    if multiplier == 2**31:
        multiplier //= 2
        shift -= 1
    if not 1 <= shift <= 62:
        raise ValueError('Requantization ratio exceeds PL shift range')
    return multiplier, shift


def requant(value, multiplier, shift):
    product = value.to(torch.int64) * multiplier
    rounded = (product.abs() + (1 << (shift - 1))) >> shift
    return torch.where(product < 0, -rounded, rounded).clamp(-127, 127)


class FixedGraph(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.channels = channels
        self.commands = commands_for(channels)
        self.layers = nn.ModuleDict()
        # Resolve the actual memory aliases once; slices and concat are views.
        memory = {}
        for channel in range(channels):
            memory[channel * plane(224)] = (-1, channel, 224)
        self.inputs = []
        for index, (src, dst, _, _, ci, co, size, stride, kernel, act) in enumerate(self.commands):
            references = [memory[int(src + channel * plane(size))] for channel in range(ci)]
            if any(ref[2] != size for ref in references):
                raise ValueError('Feature layout size mismatch')
            self.inputs.append(references)
            out_size = size // stride if kernel in (1, 3) else size // 2 if kernel == 2 else size * 2 if kernel == 0 else size
            for channel in range(co):
                memory[int(dst + channel * plane(out_size))] = (index, channel, out_size)
            if kernel in (1, 3):
                layer = nn.Conv2d(int(ci), int(co), int(kernel), int(stride), int(kernel // 2))
                nn.init.kaiming_normal_(layer.weight, a=.1)
                nn.init.zeros_(layer.bias)
                if index in HEADS:
                    with torch.no_grad():
                        layer.bias.reshape(3, 11)[:, 4] = -4.5
                self.layers[str(index)] = layer

    def source(self, values, index):
        refs = self.inputs[index]
        parts = []
        start = 0
        while start < len(refs):
            node, channel, _ = refs[start]
            end = start + 1
            while end < len(refs) and refs[end][0] == node and refs[end][1] == channel + end - start:
                end += 1
            parts.append(values[node][:, channel:channel + end - start])
            start = end
        return parts[0] if len(parts) == 1 else torch.cat(parts, 1)

    def forward(self, x, observe=None):
        values = {-1: x}
        for i, command in enumerate(self.commands):
            kernel, act = command[8:10]
            value = self.source(values, i)
            if kernel in (1, 3):
                value = self.layers[str(i)](value)
                if act:
                    value = F.leaky_relu(value, .1)
            elif kernel == 2:
                value = F.max_pool2d(value, 2)
            elif kernel == 0:
                value = F.interpolate(value, scale_factor=2, mode='nearest')
            if observe is not None:
                observe(i, value)
            values[i] = value
        return [values[i] for i in HEADS]


def manifest_for(package, channels):
    return {
        'formatVersion': 1, 'networkTemplate': 'ZYNQ7020_NEU_INT8_V1',
        'firmwareInterfaceVersion': 'CNC2-SD-25',
        'preprocessProfile': f'RGB565_{"GRAY" if channels == 1 else "RGB"}224_INT8_V1',
        'input': {'width': 224, 'height': 224, 'channels': channels, 'dtype': 'INT8'},
        'output': [[1, 33, 7, 7], [1, 33, 14, 14]],
        'classCount': 6, 'classes': CLASSES,
        'quantization': {'scheme': 'FIXED_INT8', 'inputScale': 1 / 127,
                         'inputZeroPoint': 0, 'outputScales': OUTPUT_SCALES},
        'weights': {'sha256': hashlib.sha256(package).hexdigest(), 'size': len(package)},
    }


def package_model(weights, metadata, version, channels):
    validate_payload(weights, metadata, channels)
    encoded = version.encode('ascii')
    if not 1 <= len(encoded) <= 63 or b'\0' in encoded:
        raise ValueError('Version requires 1..63 ASCII bytes without NUL')
    payload = weights + metadata
    header = struct.pack('<6I64s32s', 0x314e4e43, 1, len(weights), len(metadata), 0, 0,
                         encoded, hashlib.sha256(payload).digest())
    package = header + struct.pack('<II', zlib.crc32(header), 0) + payload
    return package, manifest_for(package, channels)


def validate_payload(weights, metadata, channels):
    if len(weights) != WEIGHT_BYTES or len(metadata) != METADATA_WORDS * 4:
        raise ValueError('Fixed graph weight/metadata size mismatch')
    words = np.frombuffer(metadata, dtype='<i4')
    if not np.array_equal(words[:330].reshape(33, 10), commands_for(channels)):
        raise ValueError('PL command template mismatch')
    for _, _, _, offset, _, co, _, _, kernel, _ in commands_for(channels):
        shifts = words[offset + 2 * co:offset + 3 * co] if kernel in (1, 3) else words[offset + 1:offset + 2] if kernel == 5 else []
        if len(shifts) and (min(shifts) < 1 or max(shifts) > 62):
            raise ValueError('PL shift must be in 1..62')
        if kernel in (1, 3):
            negative = words[offset + 4 * co:offset + 5 * co]
            if min(negative) < 1 or max(negative) > 62:
                raise ValueError('Invalid negative PL shift')


def export_int8(model, hidden_scale, version, directory):
    weights = bytearray(WEIGHT_BYTES)
    metadata = np.zeros(METADATA_WORDS, dtype='<i4')
    metadata[:330] = model.commands.reshape(-1)
    calibration = {}
    for index, (_, _, woff, moff, ci, co, _, _, kernel, act) in enumerate(model.commands):
        if kernel == 5:
            metadata[moff:moff + 2] = coefficients(1.)
        if kernel not in (1, 3):
            continue
        layer = model.layers[str(index)]
        weight = layer.weight.detach().cpu().numpy().astype(np.float64)
        ws = np.maximum(np.abs(weight).max(axis=(1, 2, 3)) / 127, 1e-12)
        quantized = np.sign(weight) * np.floor(np.abs(weight) / ws[:, None, None, None] + .5)
        packed = pack_weights(quantized.clip(-127, 127).astype('i1'))
        weights[woff:woff + len(packed)] = packed
        input_scale = 1 / 127 if index == 0 else hidden_scale
        output_scale = OUTPUT_SCALES[HEADS.index(index)] if index in HEADS else hidden_scale
        bias = layer.bias.detach().cpu().numpy().astype(np.float64) / (input_scale * ws)
        bias = np.sign(bias) * np.floor(np.abs(bias) + .5)
        # Conservative bound for every possible INT8 input, including the bias.
        bound = np.abs(quantized).sum(axis=(1, 2, 3)) * 127 + np.abs(bias)
        if not np.isfinite(bound).all() or bound.max() >= 2**31:
            raise ValueError(f'INT32 accumulator overflow at command {index}')
        metadata[moff:moff + co] = bias.astype('<i4')
        for c in range(co):
            metadata[moff + co + c], metadata[moff + 2 * co + c] = coefficients(input_scale * ws[c] / output_scale)
            metadata[moff + 3 * co + c], metadata[moff + 4 * co + c] = coefficients(input_scale * ws[c] / output_scale * (.1 if act else 1))
        calibration[str(index)] = {'inputScale': input_scale, 'outputScale': output_scale, 'weightScales': ws.tolist()}
    weights, metadata = bytes(weights), metadata.tobytes()
    package, manifest = package_model(weights, metadata, version, model.channels)
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in [('weights.bin', weights), ('metadata.bin', metadata), ('model.bin', package)]:
        (directory / name).write_bytes(data)
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (directory / 'quantization.json').write_text(json.dumps(calibration, indent=2), encoding='utf-8')
    return weights, metadata, manifest


@torch.inference_mode()
def integer_forward(model, x, weights, metadata):
    """FP64 convolutions carry bounded INT32 sums exactly; requant uses integers."""
    words = np.frombuffer(metadata, dtype='<i4').copy()
    values = {-1: x.to(torch.int64)}
    for i, (_, _, woff, moff, ci, co, _, stride, kernel, act) in enumerate(model.commands):
        value = model.source(values, i)
        if kernel in (1, 3):
            length = ((co + 47) // 48 * 48) * ((ci + 7) // 8 * 8) * kernel**2
            w = torch.from_numpy(unpack_weights(weights[woff:woff + length], co, ci, kernel)).double()
            params = torch.from_numpy(words[moff:moff + 5 * co].reshape(5, co)).to(torch.int64)
            accumulator = F.conv2d(value.double(), w, params[0].double(), stride=int(stride), padding=int(kernel // 2))
            if accumulator.abs().max() >= 2**31 or not torch.equal(accumulator, accumulator.round()):
                raise ValueError(f'Accumulator mismatch at {i}')
            pos = requant(accumulator, params[1][None, :, None, None], params[2][None, :, None, None])
            neg = requant(accumulator, params[3][None, :, None, None], params[4][None, :, None, None])
            value = torch.where(accumulator < 0, neg, pos) if act else pos
        elif kernel == 5:
            value = requant(value, int(words[moff]), int(words[moff + 1]))
        elif kernel == 2:
            value = F.max_pool2d(value.double(), 2).to(torch.int64)
        elif kernel == 0:
            value = value.repeat_interleave(2, 2).repeat_interleave(2, 3)
        values[i] = value
    return [values[i].to(torch.int8) for i in HEADS]
