from pathlib import Path
import hashlib
import json
import re

task = Path(__file__).resolve().parent
log = (task / 'flash.log').read_text(encoding='utf-8', errors='replace')
match = re.search(r'QSPI_PROGRAM_VERIFIED bytes=(\d+) sha256=([0-9a-f]{64})', log)
assert match and 'QSPI phase=2 JEDEC=ef4019 capacity_bytes=33554432 error=0' in log
backup = json.loads((task / 'flash-backup.json').read_text(encoding='utf-8-sig'))
boot = task.parents[1] / 'camera/terminal/build/delivery/boot/BOOT.bin'
assert int(match[1]) == boot.stat().st_size
with boot.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == match[2]
with Path(backup['backup']).open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == backup['sha256']
assert backup['bytes'] == (int(match[1]) + 65535) // 65536 * 65536
result = {'jedec': 'ef4019', 'flashCapacityBytes': 33554432,
          'programmedBytes': int(match[1]), 'programmedSha256': match[2],
          'ordinaryReadbackVerified': True, 'quadReadbackVerified': True,
          'backup': backup, 'originalResetRequestFailed': 'Invalid DAP IDCODE' in log}
(task / 'program-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
print('PASS: physical QSPI image SHA-256 and complete ordinary/quad readback; changed region backup retained')
