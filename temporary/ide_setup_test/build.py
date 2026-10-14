from pathlib import Path
import vitis
import build_pb2

root = Path(__file__).resolve().parents[2]
client = vitis.create_client(port=65448, workspace=(root / "vitis_live").as_posix())
try:
    if client.get_component(name="camera_live").build() != build_pb2.BuildResponse.SUCCESS:
        raise RuntimeError("Application build failed")
finally:
    client.close()
