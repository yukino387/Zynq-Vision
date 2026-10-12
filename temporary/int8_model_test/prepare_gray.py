"""Prepare fixed bicubic coefficients and an independent Pillow fixture."""
from pathlib import Path
import math
import numpy as np
from PIL import Image

directory=Path(__file__).resolve().parent / 'build'
def cubic(x):
    x=abs(x)
    if x<1: return ((1.5*x-2.5)*x)*x+1
    if x<2: return ((-.5*x+2.5)*x-4)*x+2
    return 0

rows=[]
for i in range(224):
    scale=416/224
    center=(i+.5)*scale
    start=max(0,int(center-2*scale+.5))
    end=min(416,int(center+2*scale+.5))
    values=[cubic((x-center+.5)/scale) for x in range(start,end)]
    total=sum(values)
    values=[math.trunc(v/total*(1<<22)+(.5 if v>=0 else -.5)) for v in values]
    rows.append((start,len(values),values+[0]*(8-len(values))))
text='#pragma once\n#include <stdint.h>\nstruct ResizeCoefficients { unsigned short start, count; int32_t value[8]; };\nstatic const ResizeCoefficients resize_coefficients[224]={\n'
text+=''.join('{'+str(start)+','+str(count)+',{'+','.join(map(str,values))+'}},\n' for start,count,values in rows)+'};\n'
(directory / 'gray_coefficients.h').write_text(text,encoding='ascii')
pixels=np.random.default_rng(7020).integers(0,65536,416*416,dtype=np.uint16)
r=pixels>>11; g=(pixels>>5)&63; b=pixels&31
rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=1).astype(np.uint8).reshape(416,416,3)
gray=Image.fromarray(rgb).convert('L').resize((224,224),Image.Resampling.BICUBIC)
expected=((np.asarray(gray,dtype=np.int32)*127+127)//255).astype(np.int8)
(directory / 'gray_pixels.bin').write_bytes(pixels.astype('<u2').tobytes())
(directory / 'gray_expected.bin').write_bytes(expected.tobytes())
value=2166136261
for byte in expected.tobytes(): value=((value^byte)*16777619)&0xffffffff
(directory / 'gray_expected.h').write_text(f'#pragma once\nstatic const unsigned gray_expected_hash={value}u;\n',encoding='ascii')
