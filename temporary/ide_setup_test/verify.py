import json
from pathlib import Path
import socket
import struct
import time

board = ("169.254.140.110", 5001)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3)
sock.sendto(struct.pack("<IIIi", 0x31434E43, 1, 1, 0), board)
sock.sendto(struct.pack("<IIIi", 0x31434E43, 2, 3, 0), board)
expected = {0: 75 * 13 * 13 * 2, 1: 75 * 26 * 26 * 2, 2: 416 * 416 * 2}
frames = {}
complete = set()
stats = []
deadline = time.monotonic() + 20
while time.monotonic() < deadline and len({f for f, k in complete if k == 1}) < 3:
    packet, address = sock.recvfrom(2048)
    magic = struct.unpack_from("<I", packet)[0]
    if magic == 0x31545343:
        values = struct.unpack("<11Ii", packet)
        assert values[10] == 0, values
        if values[7] > 0:
            stats.append(dict(frame=values[4], inference_ms=values[7] / 1000,
                              cycle_ms=values[9] / 1000, errors=values[10]))
    elif magic == 0x314F4C59:
        _, frame, kind, total, offset = struct.unpack_from("<5I", packet)
        assert total == expected[kind]
        buffer, offsets = frames.setdefault((frame, kind), (bytearray(total), set()))
        payload = packet[20:]
        assert offset % 1400 == 0 and len(payload) == min(1400, total - offset)
        buffer[offset:offset + len(payload)] = payload
        offsets.add(offset)
        if len(offsets) == (total + 1399) // 1400:
            complete.add((frame, kind))
assert len({f for f, k in complete if k == 1}) >= 3
first = min(f for f, k in complete if k == 1)
assert all((first, kind) in complete for kind in (0, 1, 2))
output = Path(__file__).resolve().parent / "build"
output.mkdir(exist_ok=True)
ranges = {}
for kind in (0, 1):
    buffer = frames[(first, kind)][0]
    values = struct.unpack("<" + "h" * (len(buffer) // 2), buffer)
    assert min(values) < max(values)
    ranges[f"out{kind}"] = dict(count=len(values), minimum=min(values), maximum=max(values))
    (output / f"out{kind}.bin").write_bytes(buffer)
result = dict(complete_frames=sorted({f for f, k in complete if k == 1}), outputs=ranges, stats=stats)
(output / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
sock.close()
