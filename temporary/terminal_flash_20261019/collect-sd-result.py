from pathlib import Path
import json
import re

task = Path(__file__).resolve().parent
log = (task.parent / 'terminal_qspi_20261019/uart.bin').read_bytes().decode(errors='replace')
matches = re.findall(r'^SD_FLASH_RESULT (.+)\r?$', log, re.M)
assert matches
result = json.loads(matches[-1])
plan = json.loads((task / 'flash-plan.json').read_text())
assert result['cid'] == plan['cid']
assert result['imageSha256BeforeModelRestore'] == plan['image']['sha256']
assert result['fullRawReadbackVerified'] and result['allRestoredModelHashesVerified']
assert result['restoredFiles'] == 10 and result['bootFilesVerified'] and result['partition2Present']
(task / 'sd-flash-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
print('PASS: physical SD complete image readback and all 10 restored file hashes')
