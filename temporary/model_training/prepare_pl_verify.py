import sys
from pathlib import Path
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'camera/training'))
from pl_model import FixedGraph, integer_forward
from data import preprocess
torch.set_num_threads(4)
base = Path(__file__).parent / 'artifacts'
for mode in ('GRAY', 'RGB'):
    directory = base / mode.lower()
    model = FixedGraph(1 if mode == 'GRAY' else 3)
    x = preprocess(base / 'sensor.rgb565', mode, True)
    outputs = integer_forward(model, x[None], (directory / 'weights.bin').read_bytes(), (directory / 'metadata.bin').read_bytes())
    (directory / 'verify-input.bin').write_bytes(x.numpy().tobytes())
    for i, output in enumerate(outputs):
        (directory / f'expected-out{i}.bin').write_bytes(output.numpy().tobytes())
