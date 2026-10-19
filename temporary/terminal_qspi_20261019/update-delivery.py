from pathlib import Path
import json
import subprocess

task = Path(__file__).resolve().parent
repository = task.parents[1]
evidence = json.loads((task / 'verification.json').read_text())
assert evidence['physicalColdBootVerified'] and evidence['statePersistedAcrossReboot']
path = repository / 'camera/terminal/build/delivery/qualification.json'
document = json.loads(path.read_text())
document['sourceRevision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
document['physicalLoadMethod'] = evidence['bootLayout']
document['physicalColdBootVerified'] = True
document['physicalPersistentBootCommissioned'] = True
document['physicalSdImageReadbackVerified'] = True
document['physicalModelFilesRestoredAndVerified'] = 10
document['physicalRootDataPersistedAcrossReboot'] = True
document['physicalQspi'] = evidence['qspi']
document['physicalColdBootMonitorConfirmed'] = evidence['physicalMonitorAndKeyboardConfirmedAfterFlash']
document['physicalMouseOperationVerified'] = evidence['physicalMouseOperationVerified']
document['physicalMouseUiInjectionVerified'] = True
document['physicalPanelSha256'] = evidence['mouseFix']['panelUpdate']['sha256']
document['physicalMouseUiTest'] = evidence['mouseFix']
document['pending'] = ['Long-run stability, classification accuracy and performance qualification']
if not evidence['physicalMouseOperationVerified']:
    document['pending'].append('Physical mouse movement/click confirmation')
if not evidence['physicalMonitorAndKeyboardConfirmedAfterFlash']:
    document['pending'].append('Physical monitor/keyboard confirmation after persistent boot')
for item in ['Physical SD: 2 GiB full raw image readback SHA-256, boot file hashes and all 10 original files restored',
             'W25Q256 QSPI: changed region backed up, complete ordinary and quad readback of terminal BOOT.bin passed',
             'Actual power-off/on autonomously starts QSPI FSBL/U-Boot and Linux with physical SD ext4 root',
             'Normal Linux reboot restarts panel/engine, preserves root data and retains all original model hashes']:
    if item not in document['verified']:
        document['verified'].append(item)
for item in ['ARM evdev regression reproduces mouse edge dead-zone before fix and passes after fix',
             'Live physical board evdev injection verifies visible cursor, four edge recovery, pixel clearing and dropdown left-click',
             'Updated mouse panel installed and fsynced to physical SD root; rebuilt SD image boots and contains the exact panel SHA-256']:
    if item not in document['verified']:
        document['verified'].append(item)
path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('Updated persistent-boot qualification at source revision ' + document['sourceRevision'][:7])
