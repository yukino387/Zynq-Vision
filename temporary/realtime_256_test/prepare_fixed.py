from pathlib import Path
import numpy as np
from PIL import Image

root=Path(__file__).resolve().parents[2]
test=Path(__file__).resolve().parent
image=Image.open(root/'temporary/image_inference_test/street.jpg').convert('RGB').resize((256,256),Image.Resampling.BILINEAR)
pixels=np.asarray(image,dtype=np.float32)/np.float32(255)
values=np.floor(pixels*np.float32(512)+np.float32(.5)).astype('<i2').transpose(2,0,1).copy()
folder=test/'build/fixed_files'
folder.mkdir(parents=True,exist_ok=True)
values.tofile(folder/'input.bin')
hashed=2166136261
for value in values.tobytes(): hashed=((hashed^value)*16777619)&0xffffffff
(test/'input_expected.h').write_text(f'constexpr unsigned INPUT_HASH={hashed}u;\nconstexpr int INPUT_MIN={values.min()}, INPUT_MAX={values.max()};\n',encoding='utf-8')
source=(root/'temporary/image_inference_test/main.cpp').read_text(encoding='utf-8')
source=source.replace('#include "expected.h"','#include "../full_weight_test/expected.h"')
source=source.replace('/ COUNTS_PER_SECOND','/ (COUNTS_PER_SECOND)')
(test/'fixed_main.cpp').write_text(source,encoding='utf-8')
build=(root/'temporary/operator_pipeline_test/build_fixed_image.ps1').read_text(encoding='utf-8')
build=build.replace('temporary/image_inference_test/main.cpp','temporary/realtime_256_test/fixed_main.cpp')
(test/'build_fixed.ps1').write_text(build,encoding='utf-8')
tcl=(root/'temporary/operator_pipeline_test/fixed_image.tcl').read_text(encoding='utf-8')
tcl=tcl.replace('6338','2400').replace('25350','9600')
tcl=tcl.replace('dow -data [file join $root temporary image_inference_test pc_files $file] [dict get $addresses $name]',
'''set path [file join $root temporary image_inference_test pc_files $file]
        if {$file eq "input.bin"} {set path [file join $testroot build fixed_files input.bin]}
        dow -data $path [dict get $addresses $name]''')
(test/'fixed_image.tcl').write_text(tcl,encoding='utf-8')
print('Fixed image:',values.shape,values.min(),values.max(),hex(hashed))
