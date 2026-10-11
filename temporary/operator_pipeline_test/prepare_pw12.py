from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'pw12_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'output_phases_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
# Use 48 pointwise multipliers: midway between 32 and the rejected 64.
code = (base / 'address_src/pwconv.cpp').read_text(encoding='utf-8')
assert '#define Tm 16' in code
(out / 'pwconv.cpp').write_bytes(code.replace('#define Tm 16', '#define Tm 12').encode('utf-8'))
print(out)
