from pathlib import Path
import atexit
import shutil
import sys
import vitis
import build_pb2

root=Path(__file__).resolve().parents[2]
workspace=root/'camera/terminal/build/vitis'
workspace.mkdir(parents=True,exist_ok=True)
xsa=root/'hardware/camera/build/terminal/camera_cnn.xsa'
atexit.unregister(vitis.dispose)
client=vitis.create_client(port=int(sys.argv[1]),workspace=workspace.as_posix())
name='vision_terminal_platform'
configuration=workspace/name/'vitis-comp.json'
if configuration.exists():
    platform=client.get_component(name=name)
    if xsa.stat().st_mtime>configuration.stat().st_mtime:platform.update_hw(hw_design=xsa.as_posix())
else:
    platform=client.create_platform_component(name=name,hw_design=xsa.as_posix(),os='standalone',cpu='ps7_cortexa9_0',domain_name='terminal_boot')
if platform.build()!=build_pb2.BuildResponse.SUCCESS:raise RuntimeError('Terminal boot platform build failed')
fsbl=workspace/name/'zynq_fsbl'
for filename in ['ps7_init.c','ps7_init.h']:
    shutil.copyfile(workspace/name/'export'/name/'hw/sdt'/filename,fsbl/filename)
if platform.build()!=build_pb2.BuildResponse.SUCCESS:raise RuntimeError('FSBL rebuild with terminal PS initialization failed')
if not (fsbl/'build/fsbl.elf').is_file():raise RuntimeError('Terminal FSBL is missing')
print('Terminal FSBL built from the terminal XSA')
