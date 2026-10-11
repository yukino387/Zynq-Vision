"""Prepare an isolated full-camera implementation, without replacing the working design."""
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[2]
variant = sys.argv[1]
frequency = int(sys.argv[2])
if variant not in ('combined', 'pwphase', 'output_phases') or frequency not in (100, 125):
    raise ValueError('Expected combined/pwphase/output_phases and 100/125 MHz')
base = Path(__file__).resolve().parent / 'build'
source = root / 'hardware/camera'
stage = base / f'{variant}_system_{frequency}'
stage.mkdir(parents=True, exist_ok=True)
ip = base / variant / 'solution/impl/ip'
if not (ip / 'component.xml').is_file():
    raise FileNotFoundError(ip / 'component.xml')
shutil.copytree(ip, stage / 'ip', dirs_exist_ok=True)
for name in ('base_system.tcl', 'camera.xdc', 'ov5640_capture.v'):
    shutil.copy2(source / name, stage / name)
rtl = (stage / 'ov5640_capture.v').read_text(encoding='utf-8')
(stage / 'ov5640_capture.v').write_text(rtl.replace('FREQ_HZ 100000000', f'FREQ_HZ {frequency*1000000}'), encoding='utf-8')
code = (source / 'build.tcl').read_text(encoding='utf-8')
code = code.replace('set_property ip_repo_paths C:/00_workplace/hls/xilinx_com_hls_conv_1_0 [current_project]',
                    'set_property ip_repo_paths [file join $source_dir ip] [current_project]')
code = code.replace('set ps [get_bd_cells processing_system7_0]',
                    'set ps [get_bd_cells processing_system7_0]\n'
                    f'set_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {{{frequency}}} $ps')
# Measure resource and timing closure before generating a deployable image.
code = code[:code.index('write_bitstream -force')] + 'exit\n'
(stage / 'build.tcl').write_text(code, encoding='utf-8')
print(stage / 'build.tcl')
