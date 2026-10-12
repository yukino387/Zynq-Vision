import hashlib
import sys
from pathlib import Path

# Recorded from the FPGA before moving sampling to ARM or changing cache ownership.
expected = {
    'out0.bin': (9600, '35a79ffc6ead7084996d155b988e69641eb1ee85ed84d757483357bbab8bfc99'),
    'out1.bin': (38400, '1b2c7ef700552ee5bfa5d28436426a3b5be377d9194b200087384490c6204bd0'),
}
folder = Path(sys.argv[1])
for name, (count, digest) in expected.items():
    data = (folder / name).read_bytes()
    assert len(data) == count, f'{name}: wrong size'
    assert hashlib.sha256(data).hexdigest() == digest, f'{name}: differs from FPGA baseline'
print('PASS: both prediction tensors match the original FPGA baseline byte for byte')
