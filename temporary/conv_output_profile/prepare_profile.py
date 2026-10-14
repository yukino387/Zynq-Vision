import subprocess
from pathlib import Path

test = Path(__file__).resolve().parent
root = test.parents[1]
source = test / 'build/profile_src'
source.mkdir(parents=True, exist_ok=True)
for path in (root / 'hardware/hls/src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        raw = subprocess.check_output(['git', 'show', f'45d6ce0:hardware/hls/src/{path.name}'], cwd=root)
        (source / path.name).write_bytes(raw)
path = source / 'std_conv.h'
code = path.read_text(encoding='utf-8')
code = code.replace('ap_uint<1> act, ap_uint<2> kernel);', 'ap_uint<1> act, ap_uint<2> kernel, unsigned profile_mode);')
assert 'unsigned profile_mode' in code
path.write_bytes(code.encode('utf-8'))
path = source / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
start = code.index('static void store_output(')
end = code.index('static void load_compute(', start)
raw = code[start:end].replace('static void store_output(', 'static void store_output_raw(')
raw = raw.replace('activate(buffer[lane][mm/4][rr][cc],m+mm+lane,act)', 'data_t(buffer[lane][mm/4][rr][cc])')
code = code[:end] + raw + code[end:]
code = code.replace('ap_uint<1> act, ap_uint<2> kernel){', 'ap_uint<1> act, ap_uint<2> kernel, unsigned profile_mode){')
old = '            store_output(fm_out,out1,out2,out3,out4,r,c,m,fm_size,stride,act,ch_out);'
assert code.count(old) == 1
code = code.replace(old, '''            if(profile_mode==0)
                store_output(fm_out,out1,out2,out3,out4,r,c,m,fm_size,stride,act,ch_out);
            else if(profile_mode==2)
                store_output_raw(fm_out,out1,out2,out3,out4,r,c,m,fm_size,stride,act,ch_out);''')
path.write_bytes(code.encode('utf-8'))
path = source / 'top.cpp'
code = path.read_text(encoding='utf-8')
old = 'std_conv(in1,in2,in3,in4,w1,w2,w3,w4,bias,out1,out2,out3,out4,ci,co,size,stride,act,kernel);'
assert code.count(old) == 1
code = code.replace(old, 'std_conv(in1,in2,in3,in4,w1,w2,w3,w4,bias,out1,out2,out3,out4,ci,co,size,stride,act,kernel,unsigned(act)>>1);')
path.write_bytes(code.encode('utf-8'))
print(source)
