from pathlib import Path
import subprocess
import re

root = Path(__file__).resolve().parents[2]
destination = Path(__file__).resolve().parent / "build/baseline_src"
destination.mkdir(parents=True, exist_ok=True)
for path in (root / "hardware/hls/src").iterdir():
    if path.suffix not in (".cpp", ".h"):
        continue
    source = subprocess.check_output(
        ["git", "show", "e19a41f:hardware/hls/src/" + path.name], cwd=root)
    if path.name == "top.cpp":
        # Simulation extent only; no datapath or scheduling changes.
        source = source.replace(b"m_axi port=out", b"m_axi depth=100000 port=out")
    if path.name == "std_conv.cpp":
        pattern = (rb'(?P<loads>[ \t]+tmp1=[^\n]+\n[ \t]*tmp2=[^\n]+\n'
                   rb'[ \t]*tmp3=[^\n]+\n[ \t]*tmp4=[^\n]+\n)'
                   rb'(?P<condition>[ \t]*if\(fm_row[^\n]+\)\{\r?\n)')
        source, count = re.subn(pattern, lambda m: m['condition'] + m['loads'], source)
        assert count == 2
    (destination / path.name).write_bytes(source)
print(destination)
