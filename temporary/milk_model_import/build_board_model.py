"""Convert the milk W8A8 delivery package into the board's weights.bin/metadata.bin layout."""
import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(r'C:/00_workplace/fpga/cnn_accelerator')
GRAPH = json.loads((ROOT / 'camera/training/graph.json').read_text(encoding='utf-8'))['commands']
WEIGHT_BYTES = 6350208
METADATA_WORDS = 16506
COMMAND_COUNT = 33
CHANNELS = 1

PACKAGE = Path(sys.argv[1] if len(sys.argv) > 1 else
               r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_int8_20261017/给队长_牛奶换型包_int8_20261017/牛奶_int8_w8a8')
OUTPUT = Path(sys.argv[2] if len(sys.argv) > 2 else
              r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_model_import/board_model_20261017')
VERSION = 'MILK-W8A8-20261017'
HEAD_OUTPUT_SCALES = {'out0': 0.11581249687615341, 'out1': 0.15977688286248154}


def plane(size):
    return size * (size * 8 // 7)


def pack_weights(weight):
    co, ci, k, _ = weight.shape
    padded = np.zeros(((co + 47) // 48 * 48, (ci + 7) // 8 * 8, k, k), dtype='i1')
    padded[:co, :ci] = weight
    return padded.reshape(-1, 12, 4, padded.shape[1] // 8, 8, k, k).transpose(0, 3, 2, 1, 4, 5, 6).tobytes()


def coefficients(ratio):
    mantissa, exponent = math.frexp(ratio)
    multiplier = math.floor(mantissa * 2**31 + .5)
    shift = 31 - exponent
    if multiplier == 2**31:
        multiplier //= 2
        shift -= 1
    assert 1 <= shift <= 62, (ratio, shift)
    return multiplier, shift


def commands_for(channels):
    commands = np.array(GRAPH, dtype='<i4')
    commands[0, 4] = channels
    return commands


def round_half_away(values):
    values = np.asarray(values, dtype=np.float64)
    return np.sign(values) * np.floor(np.abs(values) + .5)


def main():
    quant = json.loads((PACKAGE / 'quantization.json').read_text(encoding='utf-8'))
    package_graph = quant['graph']
    scales = dict(quant['activation_scales'])
    package_scales = dict(scales)
    layer_inputs = {node['name']: node['src'][0] for node in package_graph if node['op'] == 'conv'}
    layers = quant['layers']
    commands = commands_for(CHANNELS)
    layer_order = [node['name'] for node in package_graph if node['op'] == 'conv']
    assert len(layer_order) == 21, layer_order

    weights = bytearray(WEIGHT_BYTES)
    metadata = np.zeros(METADATA_WORDS, dtype='<i4')
    metadata[:COMMAND_COUNT * 10] = commands.reshape(-1)

    placements = {}  # output offset -> (name, channels, size)
    offset_of = {}  # output tensor name -> offset

    def out_size(size, stride):
        return size // stride if stride == 2 else size

    # Board command index -> package node name for convs, pools and the upsample.
    conv_order = [i for i, c in enumerate(commands) if c[8] in (1, 3)]
    board_name = {i: name for i, name in zip(conv_order, layer_order)}
    for index, (_, dst, _, _, _, co, size, stride, kernel, _) in enumerate(commands):
        if kernel in (1, 3):
            placements[dst] = (board_name[index], co, out_size(size, stride))
        elif kernel == 2:
            placements[dst] = (pool_name(index), co, size // 2)
        elif kernel == 0:
            placements[dst] = ('upsample', co, size * 2)
    assert len(board_name) == 21
    for offset, (name, _, _) in placements.items():
        offset_of[name] = offset

    concat_sources = {node['name']: node['src'] for node in package_graph if node['op'] == 'concat'}
    consumer = {node['name']: node['src'][0] for node in package_graph
                if node['op'] in ('conv', 'pool') and len(node.get('src', [])) == 1}

    # Each requant command converts one concat branch; the other branch stays in place and is
    # read at the concat scale by the fixed graph, so its producing layer must publish that scale.
    requant_info = []
    for index, (src, dst, _, moff, ci, _, size, _, kernel, _) in enumerate(commands):
        if kernel != 5:
            continue
        next_index = index + 1
        while commands[next_index][8] == 5:
            next_index += 1
        consumer_name = board_name.get(next_index) or pool_name(next_index)
        concat_name = consumer[consumer_name]
        sources = concat_sources[concat_name]
        buf = int(commands[next_index][0])
        first_len = placements[offset_of[sources[0]]][1] * plane(size)
        slot = 0 if dst == buf else 1 if dst == buf + first_len else None
        assert slot is not None, (index, dst, buf, first_len)
        branch = next(name for name in offset_of if offset_of[name] == src)
        assert branch == sources[slot], (index, branch, sources, slot)
        inplace = sources[1 - slot]
        # P4 requantizes both branches, so nothing is read in place there.
        if offset_of[inplace] != buf + (first_len if slot == 0 else 0):
            inplace = None
        requant_info.append((index, branch, inplace, concat_name, moff, size))
    assert len(requant_info) == 8

    scale_changes = {}
    for index, branch, inplace, concat_name, moff, size in requant_info:
        target = max(scales[name] for name in concat_sources[concat_name])
        if inplace is not None and scales[inplace] < target:
            scale_changes[inplace] = {'from': scales[inplace], 'to': target, 'concat': concat_name}
            scales[inplace] = target
    # Scales flow through aliases and copies (slice/pool/upsample); propagate until stable.
    changed = True
    while changed:
        changed = False
        for node in package_graph:
            if node['op'] in ('slice', 'pool', 'upsample'):
                target = scales[node['src'][0]]
                if scales[node['name']] != target:
                    scales[node['name']] = target
                    changed = True
    # CNN Studio and the platform manifest hard-code these head scales; emit the heads at them.
    for name, scale in HEAD_OUTPUT_SCALES.items():
        scale_changes[name] = {'from': scales[name], 'to': scale, 'reason': 'host decoder'}
        scales[name] = scale

    conv_index = 0
    for index, (src, dst, woff, moff, ci, co, size, stride, kernel, act) in enumerate(commands):
        if kernel not in (1, 3):
            continue
        name = layer_order[conv_index]
        conv_index += 1
        layer = layers[name]
        shape = tuple(layer['weight_shape'])
        assert shape == (co, ci, kernel, kernel), (index, name, shape, (co, ci, kernel))
        weight = np.fromfile(PACKAGE / layer['weight_file'], dtype='i1').reshape(shape)
        packed = pack_weights(weight)
        assert woff + len(packed) <= WEIGHT_BYTES
        weights[woff:woff + len(packed)] = packed
        bias_package = np.fromfile(PACKAGE / layer['bias_file'], dtype='<i4')
        assert bias_package.size == co
        input_package = package_scales[layer_inputs[name]]
        input_scale = scales[layer_inputs[name]]
        output_scale = scales[name]
        bias = round_half_away(bias_package.astype(np.float64) * input_package / input_scale)
        metadata[moff:moff + co] = bias.astype('<i4')
        multiplier = np.empty(co, dtype='<i4')
        shift = np.empty(co, dtype='<i4')
        negative_multiplier = np.empty(co, dtype='<i4')
        negative_shift = np.empty(co, dtype='<i4')
        for c in range(co):
            ratio = input_scale * layer['weight_scales'][c] / output_scale
            multiplier[c], shift[c] = coefficients(ratio)
            negative_multiplier[c], negative_shift[c] = coefficients(ratio * (.1 if act else 1))
        metadata[moff + co:moff + 2 * co] = multiplier
        metadata[moff + 2 * co:moff + 3 * co] = shift
        metadata[moff + 3 * co:moff + 4 * co] = negative_multiplier
        metadata[moff + 4 * co:moff + 5 * co] = negative_shift
        # Unchanged layers must reproduce the delivery parameters bit-for-bit.
        if input_scale == input_package and output_scale == layer['output_scale']:
            assert multiplier.tolist() == layer['multiplier']
            assert shift.tolist() == layer['shift']
            assert bias.tolist() == bias_package.tolist()
    assert conv_index == 21

    requant_report = {}
    for index, branch, inplace, concat_name, moff, size in requant_info:
        ratio = scales[branch] / scales[concat_name]
        multiplier, shift = coefficients(ratio)
        metadata[moff] = multiplier
        metadata[moff + 1] = shift
        requant_report[str(index)] = {'branch': branch, 'concat': concat_name, 'ratio': ratio,
                                      'multiplier': multiplier, 'shift': shift}

    metadata_bytes = metadata.tobytes()
    payload = bytes(weights) + metadata_bytes
    header = struct.pack('<6I64s32s', 0x314e4e43, 1, len(weights), len(metadata_bytes), 0, 0,
                         VERSION.encode('ascii'), hashlib.sha256(payload).digest())
    package = header + struct.pack('<II', zlib.crc32(header), 0) + payload

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'weights.bin').write_bytes(bytes(weights))
    (OUTPUT / 'metadata.bin').write_bytes(metadata_bytes)
    (OUTPUT / 'model.bin').write_bytes(package)
    manifest = {
        'version': VERSION,
        'bytes': len(package),
        'weightsSha256': hashlib.sha256(bytes(weights)).hexdigest(),
        'metadataSha256': hashlib.sha256(metadata_bytes).hexdigest(),
        'payloadSha256': hashlib.sha256(payload).hexdigest(),
        'requant': requant_report,
        'scaleChanges': scale_changes,
        'source': str(PACKAGE),
    }
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def pool_name(index):
    # board order pools are RB1.out, RB2.out, RB3.out
    order = {8: 'RB1.out', 15: 'RB2.out', 22: 'RB3.out'}
    return order[index]


if __name__ == '__main__':
    main()
