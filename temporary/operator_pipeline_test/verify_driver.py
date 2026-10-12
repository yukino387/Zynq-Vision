"""Check register ABI and prepare an isolated compile of the new driver calls."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
test = Path(__file__).resolve().parent
bsp = root / 'vitis_live/camera_platform_live/export/camera_platform_live/sw/camera_domain'
old_driver = bsp / 'hw_artifacts/drivers/conv_v1_0/src'
new_driver = test / 'build/shared44_read_lanes/solution/impl/ip/drivers/conv_v1_0/src'

def addresses(path):
    return {name:int(value,16) for name,value in re.findall(
        r'^#define XCONV_CTRL_ADDR_(\w+)\s+(0x[\da-fA-F]+)', path.read_text(), re.MULTILINE)}

old = addresses(old_driver / 'xconv_hw.h')
new = addresses(new_driver / 'xconv_hw.h')
pointers = [(f'in{i}_V',f'in{i}') for i in range(1,5)]
pointers += [(f'w{i}_V',f'w{i}_r') for i in range(1,5)]
pointers += [('b_V','b')] + [(f'out{i}_V',f'out{i}') for i in range(1,5)]
for before,after in pointers:
    assert old[before.upper()+'_DATA'] == new[after.upper()+'_DATA'], (before,after)
for name in ('AP_CTRL','GIE','IER','ISR','CH_IN_DATA','CH_OUT_DATA','FSIZE_DATA',
             'STRIDE_DATA','KERNEL_DATA','ACT_DATA'):
    assert old[name] == new[name], name
code = (root / 'basic_op.cpp').read_bytes()
for before,after in pointers:
    before = ('XConv_Set_'+before).encode()
    after = ('XConv_Set_'+after).encode()
    assert code.count(before) == 1
    code = code.replace(before,after)
out = test / 'build/driver_abi'
out.mkdir(exist_ok=True)
(out / 'basic_op.cpp').write_bytes(code)
(out / 'basic_op.h').write_bytes((root / 'basic_op.h').read_bytes())
print('PASS: all 13 pointer registers, six scalar registers and four control registers match.')
print('Prepared isolated basic_op source with generated driver names:', out)
