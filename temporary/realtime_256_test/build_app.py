from pathlib import Path
import atexit
import sys
import vitis
import build_pb2

root = Path(__file__).resolve().parents[2]
atexit.unregister(vitis.dispose)
client = vitis.create_client(port=int(sys.argv[1]))
if Path(client.get_workspace()).resolve() != (root / 'vitis_live').resolve():
    raise RuntimeError('Unexpected Vitis workspace')
if client.get_component(name='camera_live').build() != build_pb2.BuildResponse.SUCCESS:
    raise RuntimeError('Application build failed')
print('Application build passed', flush=True)
