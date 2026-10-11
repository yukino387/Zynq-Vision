import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct
import time
import numpy as np
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument("--preview", action="store_true")
parser.add_argument("--frames", type=int, default=0, help="0: continuous; positive: number of complete frames")
parser.add_argument("--output", type=Path, default=Path("temporary/camera_inference_test/received"))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
sizes = {0: 75 * 13 * 13 * 2, 1: 75 * 26 * 26 * 2, 2: 416 * 416 * 2}
required = {0, 1, 2} if args.preview else {0, 1}
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
sock.bind(("169.254.140.109", 5002))
sock.settimeout(0.5)
streams, received_frames = {}, 0
registered = 0
deadline = time.monotonic() + 600  # Initial JTAG weight download precedes the first frame.
while args.frames == 0 or received_frames < args.frames:
    now = time.monotonic()
    if now > deadline:
        raise TimeoutError("Timed out waiting for a complete camera inference frame")
    if now - registered >= 1:
        sock.sendto(bytes([int(args.preview)]), ("169.254.140.110", 5001))
        registered = now
    try:
        packet, address = sock.recvfrom(2048)
    except socket.timeout:
        continue
    if address != ("169.254.140.110", 5001) or len(packet) <= 20:
        continue
    magic, frame, kind, total, offset = struct.unpack_from("<5I", packet)
    payload = packet[20:]
    if (magic != 0x314F4C59 or kind not in required or total != sizes[kind] or
            offset % 1400 or len(payload) != min(1400, total - offset)):
        continue
    if frame not in streams:
        # Keep at most the current and previous frame; incomplete frames are dropped.
        streams = {key: value for key, value in streams.items() if key >= frame - 1}
        streams[frame] = {}
    stream = streams[frame].setdefault(kind, (bytearray(total), set()))
    stream[0][offset:offset + len(payload)] = payload
    stream[1].add(offset)
    if not all(kind in streams[frame] and len(streams[frame][kind][1]) ==
               (sizes[kind] + 1399) // 1400 for kind in required):
        continue
    folder = args.output if args.frames == 0 else args.output / f"frame_{frame:06d}"
    folder.mkdir(exist_ok=True)
    report = {"frame": frame, "streams": {}}
    for kind in sorted(required):
        raw = streams[frame][kind][0]
        name = ("out0.bin", "out1.bin", "preview_rgb565.bin")[kind]
        (folder / name).write_bytes(raw)
        values = np.frombuffer(raw, dtype="<u2" if kind == 2 else "<i2")
        report["streams"][name] = {"bytes": len(raw), "min": int(values.min()),
                                  "max": int(values.max()), "sha256": hashlib.sha256(raw).hexdigest()}
        if kind == 2:
            pixels = values.reshape(416, 416)
            red, green, blue = pixels >> 11, (pixels >> 5) & 63, pixels & 31
            rgb = np.stack(((red << 3) | (red >> 2), (green << 2) | (green >> 4),
                            (blue << 3) | (blue >> 2)), axis=-1).astype(np.uint8)
            Image.fromarray(rgb).save(folder / "preview.png")
    (folder / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    received_frames += 1
    del streams[frame]
    deadline = time.monotonic() + 120
    print(json.dumps(report), flush=True)
print(f"PASS: received {received_frames} complete frames", flush=True)
