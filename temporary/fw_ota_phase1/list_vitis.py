import sys
import vitis

port = int(sys.argv[1])
client = vitis.create_client(port=port)
client.set_workspace(r"C:/00_workplace/fpga/cnn_accelerator/vitis_live")
try:
    components = client.get_components()
    for component in components:
        print("COMPONENT", component.name, getattr(component, "type", ""))
except Exception as error:
    print("get_components failed:", error)
    for name in ("zynq_fsbl", "camera_platform_live", "camera_live"):
        try:
            component = client.get_component(name=name)
            print("COMPONENT", component.name)
        except Exception as inner:
            print("missing", name, inner)
