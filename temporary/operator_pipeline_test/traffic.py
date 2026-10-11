"""Count scheduled transfers; these counts are not measured DDR bandwidth or FPS."""
import math
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]


def constructors(file, kind):
    text = (root / file).read_text(encoding="utf-8")
    return [(name, tuple(map(int, args.split(','))))
            for name, args in re.findall(r'(\w+)\s*=\s*new '+kind+r'\(([^()]+)\)', text)
            if re.fullmatch(r'[\d,\s]+', args)]


basic = dict(constructors('cspdarknet.cpp', 'BasicConv'))
layers = [basic[name] for name in ('basic_conv1', 'basic_conv2')]
for _, (h, w, ci, co) in constructors('cspdarknet.cpp', 'Resblock_body'):
    layers += [(h,w,3,1,1,ci,co), (h,w,3,1,1,co//2,co//2),
               (h,w,3,1,1,co//2,co//2), (h,w,1,1,0,co,co)]
layers += [basic['basic_conv3']]
head = dict(constructors('yolo4_tiny.cpp', 'BasicConv'))
layers += [head['conv_forP5_conv'], head['yolo_headP5_basic_conv1'], (13,13,1,1,0,512,75),
           head['upsample_conv'], head['yolo_headP4_basic_conv1'], (26,26,1,1,0,256,75)]
assert len(layers) == 21


def count(spatial, standard, pointwise, output_phases=False, shared=False):
    reads = weights = writes = cycles = 0
    for h,w,k,s,p,ci,co in layers:
        oh, ow = (h+2*p-k)//s+1, (w+2*p-k)//s+1
        if k == 3 or shared:
            tile = min(spatial, oh)
            tiles = math.ceil(oh/tile)*math.ceil(ow/tile)
            groups = math.ceil(co/standard)
            extent = tile+k-1 if s == 1 else tile*2+1
            reads += tiles*groups*math.ceil(ci/4)*4*extent*extent*2
            phases = 1 if output_phases and co <= 32 else standard//32
            cycles += tiles*groups*math.ceil(ci/4)*tile*tile*k*k*phases
        else:
            tiles = math.ceil(oh*ow/169)
            groups = math.ceil(co/pointwise)
            reads += tiles*groups*ci*169*2
            phases = 1 if pointwise in (8,12) else 2
            cycles += tiles*groups*math.ceil(ci/4)*169*phases
        weights += tiles*ci*co*k*k*2
        writes += oh*ow*co*2
    return reads, weights, writes, cycles


for name, config in [('baseline',(13,32,8)), ('combined',(26,64,8)), ('pwphase',(26,64,16)),
                     ('output_phases',(26,64,16,True)), ('pw12',(26,64,12,True)),
                     ('pw24',(26,64,24,True)), ('shared',(26,64,64,True,True))]:
    r,w,o,c = count(*config)
    print(f'{name}: input={r/1e6:.3f} MB weights={w/1e6:.3f} MB output={o/1e6:.3f} MB '
          f'total={(r+w+o)/1e6:.3f} MB compute_lower_bound_at_125MHz={c/125000:.3f} ms')
