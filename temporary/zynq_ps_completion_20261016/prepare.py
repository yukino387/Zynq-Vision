from pathlib import Path
import shutil
out=Path('temporary/zynq_ps_completion_20261016')
for f in ['camera/camera_input.cpp','camera/create_app.py','camera/udp_output.cpp','camera/udp_output.h','camera/int8/live_main.cpp','camera/int8/weights.S','hardware/camera/build.tcl']:
 shutil.copy2(f,out/Path(f).name)
for f in ['hardware/camera/build/system_wrapper.bit','hardware/camera/build/camera_cnn.xsa']:
 shutil.copy2(f,out/Path(f).name)
p=Path('hardware/camera/build.tcl');s=p.read_text();needle='set_property CONFIG.NUM_MI 3';s=s.replace(needle,'''# QSPI boot uses the dedicated PS MIO pins; SD0 remains on MIO 40..45.
set_property -dict [list CONFIG.PCW_QSPI_PERIPHERAL_ENABLE {1} CONFIG.PCW_QSPI_QSPI_IO {MIO 1 .. 6} CONFIG.PCW_QSPI_GRP_SINGLE_SS_ENABLE {1} CONFIG.PCW_QSPI_GRP_FBCLK_ENABLE {1} CONFIG.PCW_QSPI_PERIPHERAL_FREQMHZ {50}] $ps
'''+needle);p.write_text(s)
p=Path('camera/camera_input.cpp');s=p.read_text();s=s.replace('''{0x3a02, 0x00}, {0x3a03, 0x90}, {0x3a14, 0x00}, {0x3a15, 0x90},''','''// Fixed 25 fps: 56 MHz / 1896 HTS / 1181 VTS. Force 50 Hz banding.
                  {0x380e, 0x04}, {0x380f, 0x9d}, {0x3c01, 0xb4}, {0x3c00, 0x04},
                  {0x3a02, 0x04}, {0x3a03, 0x99}, {0x3a14, 0x04}, {0x3a15, 0x99},''');p.write_text(s)
