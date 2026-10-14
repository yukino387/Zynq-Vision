import shutil
from pathlib import Path

test = Path(__file__).resolve().parent
source = test / 'build/profile_src'
source.mkdir(parents=True, exist_ok=True)
for path in (test / 'build/candidate_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, source / path.name)
path = source / 'std_conv.h'
code = path.read_text(encoding='utf-8')
code = code.replace('ap_uint<1> act, ap_uint<2> kernel);', 'ap_uint<1> act, ap_uint<2> kernel, bool output_enabled);')
assert 'bool output_enabled' in code
path.write_bytes(code.encode('utf-8'))
path = source / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
code = code.replace('ap_uint<1> act, ap_uint<2> kernel){', 'ap_uint<1> act, ap_uint<2> kernel, bool output_enabled){')
old = '            store_output(fm_out,out1,out2,out3,out4,r,c,m,fm_size,stride,act,ch_out);'
assert code.count(old) == 1
code = code.replace(old, '            if(output_enabled)\n' + old)
path.write_bytes(code.encode('utf-8'))
path = source / 'top.cpp'
code = path.read_text(encoding='utf-8')
old = 'std_conv(in1,in2,in3,in4,w1,w2,w3,w4,bias,out1,out2,out3,out4,ci,co,size,stride,act,kernel);'
assert code.count(old) == 1
code = code.replace(old, 'std_conv(in1,in2,in3,in4,w1,w2,w3,w4,bias,out1,out2,out3,out4,ci,co,size,stride,act,kernel,!(act&2));')
path.write_bytes(code.encode('utf-8'))
print(source)
