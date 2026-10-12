"""Build an isolated camera system with smaller data interconnects; no board programming."""
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[2]
base = Path(__file__).resolve().parent / 'build'
variant = sys.argv[1] if len(sys.argv) > 1 else 'compact'
assert variant in ('compact', 'pooladdr', 'shared', 'shared_dsp', 'pool_rows', 'shared44', 'shared44_narrow', 'shared44_single', 'shared44_single_fast', 'shared44_read_lanes', 'shared44_read_rows', 'shared44_weight_lanes')
frequency = float(sys.argv[2]) if len(sys.argv) > 2 else (142.857132 if variant in ('shared_dsp', 'pool_rows', 'shared44', 'shared44_narrow', 'shared44_single', 'shared44_single_fast', 'shared44_read_lanes') else 125)
assert frequency in (125,142.857132,166.666672)
stage = base / (variant+f'_area_system_{int(frequency)}')
stage.mkdir(parents=True, exist_ok=True)
ip = base / variant / 'solution/impl/ip'
if not (ip / 'component.xml').is_file():
    raise FileNotFoundError(ip / 'component.xml')
shutil.copytree(ip, stage / 'ip', dirs_exist_ok=True)
source = root / 'hardware/camera'
shutil.copy2(source / 'camera.xdc', stage / 'camera.xdc')
rtl = (source / 'ov5640_capture.v').read_text(encoding='utf-8')
assert rtl.count('FREQ_HZ 142857132') == 1
(stage / 'ov5640_capture.v').write_text(rtl.replace('FREQ_HZ 142857132',f'FREQ_HZ {round(frequency*1000000)}'), encoding='utf-8')
shutil.copy2(source / 'base_system.tcl', stage / 'base_system.tcl')
code = (source / 'build.tcl').read_text(encoding='utf-8')
code = code.replace('set_property ip_repo_paths [file join $source_dir ../hls/build/conv/solution/impl/ip] [current_project]',
                    'set_property ip_repo_paths [file join $source_dir ip] [current_project]')
code = code.replace('142.857132', str(frequency))
code = code[:code.index('phys_opt_design -directive AggressiveExplore')]+'exit\n'
(stage / 'build.tcl').write_text(code,encoding='utf-8')
print(stage / 'build.tcl')
