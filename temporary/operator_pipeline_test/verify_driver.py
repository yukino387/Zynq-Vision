"""Check register ABI and prepare an isolated compile of the new driver calls."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
test = Path(__file__).resolve().parent
new_driver = root / 'hardware/hls/build/conv/solution/impl/ip/drivers/conv_v1_0/src'

def addresses(path):
    return {name:int(value,16) for name,value in re.findall(
        r'^#define XCONV_CTRL_ADDR_(\w+)\s+(0x[\da-fA-F]+)', path.read_text(), re.MULTILINE)}

new = addresses(new_driver / 'xconv_hw.h')
pointers = [f'in{i}' for i in range(1,5)] + [f'w{i}_r' for i in range(1,5)]
pointers += ['b'] + [f'out{i}' for i in range(1,5)]
for index, name in enumerate(pointers):
    assert new[name.upper()+'_DATA'] == 0x10 + 8*index, name
for index, name in enumerate(('AP_CTRL','GIE','IER','ISR')):
    assert new[name] == 4*index, name
for index, name in enumerate(('CH_IN_DATA','CH_OUT_DATA','FSIZE_DATA','STRIDE_DATA',
                              'KERNEL_DATA','ACT_DATA')):
    assert new[name] == 0x78 + 8*index, name
code = (root / 'basic_op.cpp').read_bytes()
for name in pointers:
    assert code.count(('XConv_Set_'+name+'(').encode()) == 1, name
out = test / 'build/driver_abi'
out.mkdir(exist_ok=True)
(out / 'basic_op.cpp').write_bytes(code)
(out / 'basic_op.h').write_bytes((root / 'basic_op.h').read_bytes())
print('PASS: all 13 pointer registers, six scalar registers and four control registers match.')
print('Prepared isolated basic_op source with generated driver names:', out)
