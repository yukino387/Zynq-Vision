"""Check the promoted sources synthesize to the physically qualified RTL."""
from pathlib import Path
import re

base = Path(__file__).resolve().parent / 'build'

def contents(variant):
    result = {}
    for path in (base / variant / 'solution/syn/verilog').iterdir():
        if path.suffix in ('.v', '.dat'):
            text = path.read_text()
            if path.suffix == '.v':
                text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
            result[path.name] = re.sub(r'\s+', '', text)
    return result

qualified = contents('shared44_weight_lanes')
promoted = contents('shared44_production')
assert qualified and qualified.keys() == promoted.keys()
changed = [name for name in qualified if qualified[name] != promoted[name]]
assert not changed, changed
print(f'PASS: {len(qualified)} RTL/data files match, excluding comments and whitespace.')
