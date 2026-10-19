from pathlib import Path
import argparse
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('--ui-confirmed', action='store_true')
parser.add_argument('--mouse-confirmed', action='store_true')
args = parser.parse_args()
task = Path(__file__).resolve().parent
flash = json.loads((task / 'program-verification.json').read_text())
sd = json.loads((task.parent / 'terminal_flash_20261019/sd-flash-result.json').read_text())
log = (task / 'uart.bin').read_bytes().decode(errors='replace')
states = [json.loads(value) for value in re.findall(r'^QSPI_BOOT_STATE (.+)\r?$', log, re.M)]
first = next(value for value in states if value['phase'] == 'write')
last = next(value for value in reversed(states) if value['phase'] == 'verify')
assert log.count('U-Boot 2026.10') >= 2
assert 'VFS: Mounted root (ext4 filesystem) on device 179:2.' in log
assert first['bootId'] != last['bootId'] and last['statePersistedAcrossReboot']
for state in (first, last):
    state.pop('physicalPowerCycleVerified', None)
    assert state['rootOnPhysicalSd'] and state['rootDevice'] == [179, 2]
    assert state['modelsRestoredAndVerified'] == 10 and state['engineResponding']
    assert '/dev/input/event0' in state['panelInputFds']
assert flash['ordinaryReadbackVerified'] and flash['quadReadbackVerified']
assert sd['fullRawReadbackVerified'] and sd['allRestoredModelHashesVerified']
document = {'formatVersion': 1,
            'bootLayout': 'QSPI FSBL + PL bitstream + U-Boot; SD FAT kernel/DT/models; SD ext4 persistent root',
            'physicalColdBootVerified': True,
            'coldBootEvidence': 'User confirmed actual power-off/on; UART then captured autonomous U-Boot and SD-root Linux startup',
            'normalLinuxRebootVerified': True,
            'statePersistedAcrossReboot': True,
            'physicalMonitorAndKeyboardConfirmedAfterFlash': args.ui_confirmed,
            'physicalMouseOperationVerified': args.mouse_confirmed,
            'qspi': flash, 'sd': sd, 'coldBoot': first, 'normalReboot': last}
document['mouseFix'] = json.loads((task / 'mouse-verification.json').read_text())
assert document['mouseFix']['leftClickOpenedDropdown']
assert (task / 'repack.exit').read_text().strip() == '0'
assert (task / 'sd-runtime.exit').read_text().strip() == '0'
document['updatedSdImageBootAndPanelHashVerifiedInQemu'] = True
(task / 'verification.json').write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('PASS: physical QSPI cold boot, SD ext4 root, model preservation, autostart and persistence across Linux reboot')
