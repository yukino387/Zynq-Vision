import json
from pathlib import Path
import grpc
import debugger_pb2 as messages
import debugger_pb2_grpc as services

root = Path(__file__).resolve().parents[2]
channel = grpc.insecure_channel("localhost:65448", options=[("grpc.enable_http_proxy", 0)])
grpc.channel_ready_future(channel).result(timeout=10)
stub = services.DebuggerServiceStub(channel)
component = (root / "vitis_live/camera_live").as_posix()
print("Starting Vitis Run initialization", flush=True)
stub.setupSystemLaunchJson(messages.SetupSystemLaunchJsonRequest(
    componentPath=component, createNew=False, debug=False,
    launchName="camera_live", id="camera-live-verification"), timeout=300)
print("Vitis Run initialization succeeded", flush=True)
