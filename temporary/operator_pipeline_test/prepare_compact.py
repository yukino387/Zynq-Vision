from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'compact_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'pw24_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
old = '#pragma HLS BIND_OP variable=row_offset op=mul impl=fabric latency=3'
assert code.count(old) == 1
path.write_bytes(code.replace(old, old.replace('impl=fabric','impl=dsp')).encode('utf-8'))
print(out)
