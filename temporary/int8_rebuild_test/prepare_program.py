"""Pack aligned features and tiled weights for PS scheduled gray224 inference."""
from pathlib import Path
import json
import math
import struct
import numpy as np
import shutil

directory = Path(__file__).resolve().parent
(directory / 'build').mkdir(exist_ok=True)
golden = directory.parent / 'int8_model_test/build/golden'
quant = json.loads((golden / 'quantization.json').read_text())
commands = []
command_names = []
metadata = [0] * 640
weights = bytearray()
def pitch(size): return 1 << (size-1).bit_length()
def plane(size): return size*pitch(size)
input_data=np.zeros((224,256),dtype=np.int8)
input_data[:,:224]=np.frombuffer((golden/'input.bin').read_bytes(),dtype=np.int8).reshape(224,224)
features=bytearray(input_data.tobytes())
nodes = {'input': (0,1,224)}
checks = []

def allocate(channels, size):
    offset = (len(features)+63) & ~63
    features.extend(bytes(offset + channels*plane(size)-len(features)))
    return offset

def coefficients(ratio):
    mantissa, exponent = math.frexp(ratio)
    multiplier = math.floor(mantissa*2**31+.5)
    shift = 31-exponent
    if multiplier == 2**31:
        multiplier //= 2
        shift -= 1
    return multiplier, shift

shapes = {'input': (1,224)}
for node in quant['graph']:
    ci,size = shapes[node['src'][0]]
    op = node['op']
    if op == 'conv':
        co = quant['layers'][node['name']]['weight_shape'][0]
        size //= node['stride']
    elif op == 'slice': co = ci-node['start']
    elif op == 'concat': co = sum(shapes[src][0] for src in node['src'])
    else:
        co = ci
        size = size//2 if op=='pool' else size*2
    shapes[node['name']] = co,size

# Write a branch with the same quantization scale directly into its concat slot.
fixed = {}
for node in quant['graph']:
    if node['op'] != 'concat': continue
    co,size = shapes[node['name']]
    destination = allocate(co,size)
    fixed[node['name']] = destination
    for src in node['src']:
        if src not in fixed and quant['activation_scales'][src] == quant['activation_scales'][node['name']]:
            fixed[src] = destination
        destination += shapes[src][0]*plane(size)

for node in quant['graph']:
    name, op = node['name'], node['op']
    source, ci, size = nodes[node['src'][0]]
    if op == 'slice':
        output, co, out_size = source+node['start']*plane(size), ci-node['start'], size
    elif op == 'conv':
        params = quant['layers'][name]
        co = params['weight_shape'][0]
        out_size = size // node['stride']
        output = fixed[name] if name in fixed else allocate(co,out_size)
        weight_offset = len(weights)
        ci_padded=(ci+7)//8*8
        co_padded=(co+47)//48*48
        kk=node['k']**2
        packed=np.zeros((co_padded,ci_padded,kk),dtype=np.int8)
        packed[:co,:ci,:]=np.frombuffer((golden/params['weight_file']).read_bytes(),dtype=np.int8).reshape(co,ci,kk)
        packed=packed.reshape(co_padded//48,12,4,ci_padded//8,8,kk).transpose(0,3,2,1,4,5)
        weights.extend(packed.tobytes())
        meta_offset = len(metadata)
        bias = (golden / params['bias_file']).read_bytes()
        metadata.extend(struct.unpack('<'+'i'*co, bias))
        for key in ('multiplier','shift','negative_multiplier','negative_shift'):
            metadata.extend(params[key])
        command_names.append(name)
        commands.append([source,output,weight_offset,meta_offset,ci,co,size,node['stride'],node['k'],int(node['act'])])
    elif op == 'concat':
        co = sum(nodes[src][1] for src in node['src'])
        out_size = size
        output = fixed[name]
        destination = output
        for src in node['src']:
            offset, count, _ = nodes[src]
            if offset != destination:
                meta_offset = len(metadata)
                metadata.extend(coefficients(quant['activation_scales'][src]/quant['activation_scales'][name]))
                command_names.append(name+'/'+src)
                commands.append([offset,destination,0,meta_offset,count,count,size,1,5,0])
            else:
                assert quant['activation_scales'][src] == quant['activation_scales'][name]
            destination += count*plane(size)
    elif op in ('pool','upsample'):
        co = ci
        out_size = size//2 if op=='pool' else size*2
        output = fixed[name] if name in fixed else allocate(co,out_size)
        command_names.append(name)
        commands.append([source,output,0,0,ci,co,size,1,2 if op=='pool' else 0,0])
    else:
        raise ValueError(op)
    nodes[name] = (output,co,out_size)
    checks.append((name,output,co,out_size))

(directory / 'build/command_names.json').write_text(json.dumps(command_names))
assert len(commands) <= 64
assert all(command[0] % 8 == 0 and command[1] % 8 == 0 and command[2] % 8 == 0 for command in commands)
for i, command in enumerate(commands):
    metadata[i*10:i*10+10] = command
(directory / 'build/weights.bin').write_bytes(weights)
(directory / 'build/metadata.bin').write_bytes(struct.pack('<'+'i'*len(metadata),*metadata))
(directory / 'build/features.bin').write_bytes(features)
header = f'''#pragma once
#include <stdint.h>
static const unsigned command_count={len(commands)}, feature_bytes={len(features)}, weight_bytes={len(weights)}, metadata_words={len(metadata)};
static const unsigned out0_offset={nodes['out0'][0]}, out1_offset={nodes['out1'][0]};
struct Check {{ const char* name; unsigned offset, channels, size; }};
static const Check checks[]={{
'''
header += ''.join(f'    {{"{name}",{offset},{channels},{size}}},\n' for name,offset,channels,size in checks) + '};\n'
hashes = []
for name, _, _, _ in checks:
    value = 2166136261
    for byte in (golden / (name+'.bin')).read_bytes():
        value = ((value ^ byte)*16777619) & 0xffffffff
    hashes.append(value)
header += 'static const uint32_t expected_hashes[]={'+','.join(str(h)+'u' for h in hashes)+'};\n'
(directory / 'build/model.h').write_text(header, encoding='utf-8')
(directory / 'build/layout.tcl').write_text(
    f'set command_count {len(commands)}\nset out0_offset {nodes["out0"][0]}\nset out1_offset {nodes["out1"][0]}\n', encoding='ascii')
config = f'''part=xc7z020clg400-2
[hls]
flow_target=vivado
clock=7
syn.top=conv
syn.interface.m_axi_addr64=0
csim.code_analyzer=0
'''
for name in ('top','std_conv','maxpool','upsample'):
    config += f'syn.file={(directory.parents[1] / "hardware/hls/src" / (name+".cpp")).as_posix()}\n'
config += f'tb.file={(directory / "test.cpp").as_posix()}\n'
(directory / 'hls_config.cfg').write_text(config,encoding='utf-8')
print(f'{len(commands)} PL commands, {len(weights)} weight bytes, {len(features)} feature bytes, {len(metadata)*4} metadata bytes')

for name in ('gray_coefficients.h','gray_expected.h','gray_pixels.bin'):
    shutil.copy2(directory.parent/'int8_model_test/build'/name,directory/'build'/name)
