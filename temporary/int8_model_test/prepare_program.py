"""Build a fixed PL command list and binary weights for the gray224 model."""
from pathlib import Path
import json
import math
import struct

directory = Path(__file__).resolve().parent
golden = directory / 'build/golden'
quant = json.loads((golden / 'quantization.json').read_text())
commands = []
metadata = [0] * 640
weights = bytearray()
features = bytearray((golden / 'input.bin').read_bytes())
nodes = {'input': (0,1,224)}
checks = []

def allocate(channels, size):
    offset = (len(features)+63) & ~63
    features.extend(bytes(offset + channels*size*size-len(features)))
    return offset

def coefficients(ratio):
    mantissa, exponent = math.frexp(ratio)
    multiplier = math.floor(mantissa*2**31+.5)
    shift = 31-exponent
    if multiplier == 2**31:
        multiplier //= 2
        shift -= 1
    return multiplier, shift

for node in quant['graph']:
    name, op = node['name'], node['op']
    source, ci, size = nodes[node['src'][0]]
    if op == 'slice':
        output, co, out_size = source+node['start']*size*size, ci-node['start'], size
    elif op == 'conv':
        params = quant['layers'][name]
        co = params['weight_shape'][0]
        out_size = size // node['stride']
        output = allocate(co, out_size)
        weight_offset = len(weights)
        weights.extend((golden / params['weight_file']).read_bytes())
        meta_offset = len(metadata)
        bias = (golden / params['bias_file']).read_bytes()
        metadata.extend(struct.unpack('<'+'i'*co, bias))
        for key in ('multiplier','shift','negative_multiplier','negative_shift'):
            metadata.extend(params[key])
        commands.append([source,output,weight_offset,meta_offset,ci,co,size,node['stride'],node['k'],int(node['act'])])
    elif op == 'concat':
        co = sum(nodes[src][1] for src in node['src'])
        out_size = size
        output = allocate(co, size)
        destination = output
        for src in node['src']:
            offset, count, _ = nodes[src]
            meta_offset = len(metadata)
            metadata.extend(coefficients(quant['activation_scales'][src]/quant['activation_scales'][name]))
            commands.append([offset,destination,0,meta_offset,count,count,size,1,5,0])
            destination += count*size*size
    elif op in ('pool','upsample'):
        co = ci
        out_size = size//2 if op=='pool' else size*2
        output = allocate(co,out_size)
        commands.append([source,output,0,0,ci,co,size,1,2 if op=='pool' else 0,0])
    else:
        raise ValueError(op)
    nodes[name] = (output,co,out_size)
    checks.append((name,output,co*out_size*out_size))

assert len(commands) <= 64
for i, command in enumerate(commands):
    metadata[i*10:i*10+10] = command
(directory / 'build/weights.bin').write_bytes(weights)
(directory / 'build/metadata.bin').write_bytes(struct.pack('<'+'i'*len(metadata),*metadata))
(directory / 'build/features.bin').write_bytes(features)
header = f'''#pragma once
#include <stdint.h>
static const unsigned command_count={len(commands)}, feature_bytes={len(features)}, weight_bytes={len(weights)}, metadata_words={len(metadata)};
static const unsigned out0_offset={nodes['out0'][0]}, out1_offset={nodes['out1'][0]};
struct Check {{ const char* name; unsigned offset, count; }};
static const Check checks[]={{
'''
header += ''.join(f'    {{"{name}",{offset},{count}}},\n' for name,offset,count in checks) + '};\n'
hashes = []
for name, _, _ in checks:
    value = 2166136261
    for byte in (golden / (name+'.bin')).read_bytes():
        value = ((value ^ byte)*16777619) & 0xffffffff
    hashes.append(value)
header += 'static const uint32_t expected_hashes[]={'+','.join(str(h)+'u' for h in hashes)+'};\n'
(directory / 'build/model.h').write_text(header, encoding='utf-8')
(directory / 'build/layout.tcl').write_text(
    f'set out0_offset {nodes["out0"][0]}\nset out1_offset {nodes["out1"][0]}\n', encoding='ascii')
config = f'''part=xc7z020clg400-2
[hls]
flow_target=vivado
clock=7
syn.top=conv
syn.interface.m_axi_addr64=0
csim.code_analyzer=0
'''
for name in ('top','std_conv','maxpool','upsample'):
    config += f'syn.file={(directory / "src" / (name+".cpp")).as_posix()}\n'
config += f'tb.file={(directory / "test.cpp").as_posix()}\n'
(directory / 'hls_config.cfg').write_text(config,encoding='utf-8')
print(f'{len(commands)} PL commands, {len(weights)} weight bytes, {len(features)} feature bytes, {len(metadata)*4} metadata bytes')
