from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'pooladdr_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'compact_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'maxpool.cpp'
code = path.read_text(encoding='utf-8')
before, store = code.split('void store_output', 1)
old = '#pragma HLS BIND_OP variable=n_base op=mul impl=fabric latency=3'
assert store.count(old) == 1
path.write_bytes((before+'void store_output'+store.replace(old, old.replace('impl=fabric','impl=dsp'))).encode('utf-8'))
print(out)
