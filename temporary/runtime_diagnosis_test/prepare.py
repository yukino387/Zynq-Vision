from pathlib import Path
import json

root = Path(__file__).resolve().parents[2]
test = Path(__file__).resolve().parent
old = root / 'temporary/bottleneck_test'
cases = json.loads((old / 'probes.json').read_text()) + [
    [1, 4, 14, 1, 3], [1, 48, 14, 1, 3],
    [1, 4, 7, 1, 3], [1, 48, 7, 1, 3],
    [512, 4, 14, 1, 1], [512, 48, 14, 1, 1],
    [128, 4, 28, 1, 1], [128, 48, 28, 1, 1],
    [128, 48, 28, 1, 3], [8, 48, 14, 1, 1],
    [8, 48, 14, 1, 3], [512, 4, 28, 1, 1],
]
count = len(cases)
source = (old / 'board.cpp').read_text()
source = source.replace('probe_us[19][3]', f'probe_us[{count}][3]')
start = source.index('    const unsigned cases[19][5]=')
end = source.index(';', start) + 1
initializer = ','.join('{' + ','.join(map(str, c)) + '}' for c in cases)
source = source[:start] + f'    const unsigned cases[{count}][5]={{{initializer}}};' + source[end:]
source = source.replace('probe<19', f'probe<{count}')
(test / 'board.cpp').write_text(source)
(test / 'probes.json').write_text(json.dumps(cases, indent=2) + '\n')
(test / 'build_board.ps1').write_text((old / 'build_board.ps1').read_text())
tcl = (old / 'run_board.tcl').read_text().replace('temporary bottleneck_test build', 'temporary runtime_diagnosis_test build')
tcl = tcl.replace('probe_us 57', f'probe_us {count * 3}')
tcl = tcl.replace('guards intact.', f'guards intact; {count} controlled probes passed output and guard checks.')
(test / 'run_board.tcl').write_text(tcl)
print(f'Prepared {count} probes; formal hardware and software unchanged')
