from pathlib import Path
import base64
import hashlib
import json
import re
import zlib
from PIL import Image

task = Path(__file__).resolve().parent
log = (task / 'uart.bin').read_bytes().decode(errors='replace')
result = json.loads(re.findall(r'^MOUSE_UI_RESULT (.+)\r?$', log, re.M)[-1])
update = json.loads(re.findall(r'^PANEL_UPDATE (.+)\r?$', log, re.M)[-1])
events = json.loads(re.findall(r'^USB_INPUT_EVENTS (.+)\r?$', log, re.M)[-1])
frame = zlib.decompress(base64.b64decode(re.findall(r'^MOUSE_UI_FRAME (.+)\r?$', log, re.M)[-1]))
assert len(frame) == 1280 * 720 * 4
assert hashlib.sha256(frame).hexdigest() == result['frameSha256']
assert all(result[name] for name in ['leftTopRecovery', 'rightBottomRecovery', 'cursorVisible',
                                     'oldCursorPixelsCleared', 'leftClickOpenedDropdown'])
assert int((task / 'evdev-edge-before.exit').read_text()) != 0
assert (task / 'evdev-edge-after.exit').read_text().strip() == '0'
assert 'EVDEV_EDGE_RECOVERY_PASSED' in (task / 'evdev-edge-after.log').read_text(errors='replace')
Image.frombytes('RGB', (1280, 720), frame, 'raw', 'BGRX').save(task / 'mouse-ui-frame.png')
result.update({'physicalInputEventsBeforeFix': events, 'panelUpdate': update,
               'armEdgeRegressionFailedBeforeFix': True, 'armEdgeRegressionPassedAfterFix': True})
(task / 'mouse-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
print('PASS: real mouse events, ARM edge regression and live-board cursor/click injection; framebuffer PNG saved')
