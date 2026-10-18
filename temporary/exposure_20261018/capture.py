import sys, time, struct, json
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'camera'))
from board_control import Board

label = sys.argv[1]
board = Board()
original = board.command(0)
frames = {}
images = []
errors = []
try:
    board.command(1)
    board.command(3, 1)
    end = time.monotonic() + 6
    board.s.settimeout(1)
    while time.monotonic() < end:
        try:
            packet, remote = board.s.recvfrom(65536)
        except TimeoutError:
            continue
        if remote != board.peer:
            continue
        if len(packet) == 48 and struct.unpack_from('<I', packet)[0] == 0x31545343:
            status = struct.unpack('<11Ii', packet)
            if status[10]: errors.append(status[10])
        if len(packet) < 20 or struct.unpack_from('<I', packet)[0] != 0x314f4c59:
            continue
        _, frame, kind, total, offset = struct.unpack_from('<5I', packet)
        if kind != 2 or total != 346112:
            continue
        data, offsets = frames.setdefault(frame, (bytearray(total), set()))
        data[offset:offset+len(packet)-20] = packet[20:]
        offsets.add(offset)
        if len(offsets) == 248:
            images.append(bytes(data))
            del frames[frame]
        if len(frames) > 8: del frames[next(iter(frames))]
    if not images: raise RuntimeError('No complete frames')
    pixel = np.frombuffer(images[-1], dtype='<u2').reshape(416, 416).astype(np.uint32)
    rgb = np.stack([((pixel >> 11) & 31) * 255 // 31, ((pixel >> 5) & 63) * 255 // 63, (pixel & 31) * 255 // 31], axis=-1).astype(np.uint8)
    Image.fromarray(rgb).save(Path(__file__).with_name(label + '.png'))
    report = {'frames':len(images), 'errors':errors, 'brightness':original[-1], 'meanRgb':rgb.mean(axis=(0,1)).tolist(), 'whiteClippedPercent':float(np.mean(np.all(rgb >= 247, axis=-1))*100), 'anyChannelClippedPercent':float(np.mean(np.any(rgb >= 247, axis=-1))*100)}
    Path(__file__).with_name(label + '.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
finally:
    board.command(3, int(bool(original[3] & 2)))
    board.command(2, int(bool(original[3] & 1)))
    board.s.close()
