"""Short camera and W8A8 network measurement over UDP."""
import json
import argparse
import socket
import statistics
import struct
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--detect-only', action='store_true',
                    help='Measure prediction tensors without image preview')
args = parser.parse_args()
peer = ('169.254.140.110', 5001)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('169.254.140.109', 5003))
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
sock.settimeout(0.5)
request = 0
stats = []
frames = {}
completed = []
phase = 'startup'
sizes = {0: 33 * 7 * 7, 1: 33 * 14 * 14, 2: 416 * 416 * 2}

def receive():
    try:
        data, sender = sock.recvfrom(2048)
    except socket.timeout:
        return None
    if sender != peer:
        return None
    if len(data) == 48 and data[:4] == b'CST1':
        row = struct.unpack('<11Ii', data)
        stats.append({'phase': phase, 'status': row})
        if row[10]:
            raise RuntimeError(f'Board reported error {row[10]} in {phase}: {row}')
        return row
    if len(data) > 20 and data[:4] == b'YLO1':
        _, frame, kind, size, offset = struct.unpack('<5I', data[:20])
        assert kind in sizes and size == sizes[kind]
        assert offset % 1400 == 0 and len(data) - 20 == min(1400, size - offset)
        entry = frames.setdefault(frame, {})
        entry.setdefault(kind, set()).add(offset)
        required = (2,) if phase == 'preview' else ((0, 1) if args.detect_only else (0, 1, 2))
        if all(k in entry and len(entry[k]) == (sizes[k] + 1399) // 1400 for k in required):
            completed.append((phase, frame, time.monotonic()))
            for old in list(frames):
                if old <= frame:
                    del frames[old]
    return None

def command(number, value):
    global request
    request += 1
    packet = struct.pack('<IIIi', 0x31434e43, request, number, value)
    for _ in range(8):
        sock.sendto(packet, peer)
        end = time.monotonic() + 1
        while time.monotonic() < end:
            row = receive()
            if row and row[1] == request:
                return row
    raise TimeoutError(f'Board command {number} received no acknowledgement')

try:
    print('discover', command(0, 0), flush=True)
    if args.detect_only:
        sock.sendto(b'\0', peer)
        print('connect without preview', command(0, 0), flush=True)
    else:
        print('connect', command(1, 0), flush=True)
    phases = (('detect', 0, 3),) if args.detect_only else (('detect', 0, 3), ('preview', 1, 2))
    for phase, mode, duration in phases:
        print('mode', phase, command(3, mode), flush=True)
        frames.clear()
        end = time.monotonic() + duration
        while time.monotonic() < end:
            receive()
        rows = [x['status'] for x in stats if x['phase'] == phase and x['status'][1] == 0
                and bool(x['status'][3] & 2) == bool(mode) and x['status'][9] > 0][3:]
        assert len(rows) >= 10, f'{phase}: only {len(rows)} valid timing samples'
        timings = dict(zip(('capture_us', 'convert_us', 'infer_us', 'send_us', 'cycle_us'),
                          (statistics.median(r[i] for r in rows) for i in range(5, 10))))
        received = [r for r in completed if r[0] == phase][3:]
        assert len(received) >= 10, f'{phase}: only {len(received)} complete frames'
        fps = (len(received) - 1) / (received[-1][2] - received[0][2])
        print(phase, 'samples', len(rows), 'median', timings, 'received_fps', fps, flush=True)
        if phase == 'preview':
            assert fps >= 10, f'Camera preview is below 10 FPS: {fps:.2f}'
    print('detect restore', command(3, 0), flush=True)
    print('pause before receiver closes', command(2, 0), flush=True)
finally:
    Path(__file__).resolve().parent.joinpath('build/short_udp_results.json').write_text(
        json.dumps({'preview_enabled': not args.detect_only, 'stats': stats, 'frames': completed}, indent=2))
    sock.close()
