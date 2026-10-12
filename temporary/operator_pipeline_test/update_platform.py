"""Update the existing Vitis platform to the qualified camera hardware."""
from pathlib import Path
import atexit
import sys
import vitis
import build_pb2

root = Path(__file__).resolve().parents[2]
atexit.unregister(vitis.dispose)
client = vitis.create_client(port=int(sys.argv[1]))
if Path(client.get_workspace()).resolve() != (root / 'vitis_live').resolve():
    raise RuntimeError('The IDE server is using a different workspace')
client.set_embedded_sw_repo(level='LOCAL', path=[
    'C:/AMDDesignTools/2026.1/Vitis/data/embeddedsw',
    (root / 'camera/build/lwip_repo').as_posix()])
platform = client.get_component(name='camera_platform_live')
platform.update_hw(hw_design=(root / 'hardware/camera/build/camera_cnn.xsa').as_posix())
domain = platform.get_domain('camera_domain')
domain.set_lib(lib_name='lwip220')
domain.set_config(option='lib', lib_name='lwip220', param='lwip220_api_mode', value='RAW_API')
domain.set_config(option='lib', lib_name='lwip220', param='lwip220_dhcp', value='false')
domain.set_config(option='lib', lib_name='lwip220', param='lwip220_tcp', value='false')
if platform.build() != build_pb2.BuildResponse.SUCCESS:
    raise RuntimeError('Updated platform build failed')
app = client.get_component(name='camera_live')
if app.build() != build_pb2.BuildResponse.SUCCESS:
    raise RuntimeError('Application build with the new Conv driver failed')
print(root / 'vitis_live/camera_live/build/camera_live.elf')
