from pathlib import Path
import argparse
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('--screen-confirmed', action='store_true')
parser.add_argument('--keyboard-confirmed', action='store_true')
args = parser.parse_args()
task = Path(__file__).resolve().parent
repository = task.parents[1]
delivery = repository / 'camera/terminal/build/delivery'
for name in ['boot-build', 'load', 'sd-build', 'sd-runtime']:
    assert (task / (name + '.exit')).read_text().strip() == '0', name
log = (task / 'uart.bin').read_bytes().decode(errors='replace')
boot = log.rsplit('Starting kernel', 1)[-1]
matches = re.findall(r'^USB_BOARD_STATE (.+)\r?$', boot, re.M)
assert matches, 'Missing post-reboot board snapshot'
board = json.loads(matches[-1])
assert any(x['idVendor'] == '05e3' and x['idProduct'] == '0608' for x in board['usbDevices'])
assert any(x['idVendor'] == '0c45' and x['idProduct'] == 'fefe' for x in board['usbDevices'])
assert '/dev/input/event0' in board['inputNodes']
assert board['panel'] and '/dev/input/event0' in board['panel'][0]['inputFds']
assert 'out hi ACTIVE LOW' in board['gpio']
assert not int(board['mio']['0x724'], 16) & 1
assert int(board['vdma']['0x0'], 16) & 1
assert 'USB HID v1.00 Keyboard' in boot
assert b'PASS: packaged U-Boot ELF' in (task / 'sd-runtime.log').read_bytes()
event_matches = re.findall(r'USB_INPUT_EVENTS (\{[^\r\n]+\})', boot)
events = json.loads(event_matches[-1]) if event_matches else None
document = {
    'formatVersion': 1,
    'cause': 'USB3320 reset polarity was inverted; MIO9 also lacked explicit GPIO pin configuration',
    'fix': 'BAS16 diode reset uses GPIO_ACTIVE_LOW; configure MIO9 as GPIO with bias-disable',
    'loadMethod': 'Full JTAG PS reset and RAM boot with rebuilt device tree and U-Boot; physical SD/QSPI untouched',
    'automaticUsbEnumerationAfterReboot': True,
    'panelOpenedKeyboardEvdev': True,
    'physicalHdmiPictureConfirmedBeforeReload': True,
    'physicalHdmiPictureConfirmedAfterReload': args.screen_confirmed,
    'physicalKeyboardUiConfirmed': args.keyboard_confirmed,
    'physicalMouseConnected': False,
    'physicalMouseOperationVerified': False,
    'inputEventCapture': events,
    'qemuSdBootKeyboardPassed': True,
    'dtbSha256': hashlib.sha256((delivery / 'boot/system.dtb').read_bytes()).hexdigest(),
    'board': board,
}
(task / 'verification.json').write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('PASS: automatic physical USB enumeration, panel keyboard fd, reset polarity, GPIO pin state, running HDMI scanout and SD boot simulation')
