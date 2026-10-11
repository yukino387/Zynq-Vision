"""Build an isolated camera system with smaller data interconnects; no board programming."""
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[2]
base = Path(__file__).resolve().parent / 'build'
variant = sys.argv[1] if len(sys.argv) > 1 else 'compact'
assert variant in ('compact', 'pooladdr', 'shared', 'shared_dsp', 'pool_rows')
frequency = 142.857132 if variant in ('shared_dsp', 'pool_rows') else 125
stage = base / (variant+f'_area_system_{int(frequency)}')
stage.mkdir(parents=True, exist_ok=True)
ip = base / variant / 'solution/impl/ip'
if not (ip / 'component.xml').is_file():
    raise FileNotFoundError(ip / 'component.xml')
shutil.copytree(ip, stage / 'ip', dirs_exist_ok=True)
source = root / 'hardware/camera'
shutil.copy2(source / 'camera.xdc', stage / 'camera.xdc')
rtl = (source / 'ov5640_capture.v').read_text(encoding='utf-8')
(stage / 'ov5640_capture.v').write_text(rtl.replace('FREQ_HZ 100000000',f'FREQ_HZ {round(frequency*1000000)}'), encoding='utf-8')
code = (source / 'base_system.tcl').read_text(encoding='utf-8')
for index in range(4):
    name = f'smartconnect_{index}'
    old = f'set {name} [ create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 {name} ]'
    assert old in code
    new = old.replace('smartconnect:1.0','axi_interconnect:2.1')
    new += f'\n  set_property -dict [list CONFIG.NUM_SI {{2}} CONFIG.NUM_MI {{1}} CONFIG.STRATEGY {{1}}] ${name}'
    code = code.replace(old,new).replace(name+'/aclk',name+'/ACLK').replace(name+'/aresetn',name+'/ARESETN')
    for pin in ('S00','S01','M00'):
        connection = f'\n  connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins {name}/{pin}_ACLK]\n'
        connection += f'  connect_bd_net [get_bd_pins rst_ps7_0_50M/peripheral_aresetn] [get_bd_pins {name}/{pin}_ARESETN]\n'
        code = code.replace('  # Create address segments',connection+'  # Create address segments')
(stage / 'base_system.tcl').write_text(code,encoding='utf-8')
code = (source / 'build.tcl').read_text(encoding='utf-8')
code = code.replace('set_property ip_repo_paths C:/00_workplace/hls/xilinx_com_hls_conv_1_0 [current_project]',
                    'set_property ip_repo_paths [file join $source_dir ip] [current_project]')
code = code.replace('set ps [get_bd_cells processing_system7_0]',
                    f'set ps [get_bd_cells processing_system7_0]\nset_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {{{frequency}}} $ps')
code = code.replace('validate_bd_design',
                    'connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins smartconnect_0/S02_ACLK]\n'
                    'connect_bd_net [get_bd_pins rst_ps7_0_50M/peripheral_aresetn] [get_bd_pins smartconnect_0/S02_ARESETN]\nvalidate_bd_design')
code = code.replace('save_bd_design',
                    'set actual_frequency [get_property CONFIG.PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ $ps]\n'
                    f'if {{abs($actual_frequency-{frequency}) > 0.001}} {{error "Unexpected actual FCLK frequency: $actual_frequency"}}\n'
                    'puts "ACTUAL_FCLK_MHZ=$actual_frequency"\nsave_bd_design')
code = code[:code.index('write_bitstream -force')]+'exit\n'
(stage / 'build.tcl').write_text(code,encoding='utf-8')
print(stage / 'build.tcl')
