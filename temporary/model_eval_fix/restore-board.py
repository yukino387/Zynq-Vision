import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'camera'))
from board_control import Board

original = json.loads(Path(__file__).with_name('baseline.json').read_text())['device']
board = Board(local_port=5004)
try:
    board.command(1)
    board.command(2, 0)
    active = board.call(0)
    entries = [board.call(7, index) for index in range(active['total'])]
    target = next(entry for entry in entries if entry['version'] == original['reportedState']['modelVersion'] and entry['sha256'] == original['reportedState']['modelPayloadSha256'])
    board.call(8, target['received'])
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status = board.call(0)
        if status['version'] == target['version'] and status['sha256'] == target['sha256'] and status['flags'] & 11 == 11 and not status['flags'] & 16:
            break
        time.sleep(.1)
    else:
        raise RuntimeError(f'Recovery not confirmed: {status}')
    board.command(3, int(original['reportedState']['cameraOnly']))
    board.command(2, int(original['runtimeState'] == 'RUNNING'))
    print(json.dumps(status))
finally:
    board.s.close()
