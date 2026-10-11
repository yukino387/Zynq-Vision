from pathlib import Path
import shutil
import stat
import vitis

root = Path(__file__).resolve().parents[1]
workspace = root / "camera" / "build" / "workspace"
workspace.mkdir(parents=True, exist_ok=True)
library_source = Path("C:/AMDDesignTools/2026.1/Vitis/data/embeddedsw/ThirdParty/sw_services/lwip220_v1_4")
library_copy = root / "camera/build/lwip_repo/lwip220_v1_4"
if not library_copy.exists():
    shutil.copytree(library_source, library_copy)
schema = library_copy / "data/lwip220.yaml"
schema.chmod(stat.S_IREAD | stat.S_IWRITE)
schema.write_text(schema.read_text(encoding="utf-8-sig"), encoding="utf-8")
client = vitis.create_client(port=51123, workspace=workspace.as_posix())
client.set_embedded_sw_repo(level="LOCAL", path=["C:/AMDDesignTools/2026.1/Vitis/data/embeddedsw",
    (root / "camera/build/lwip_repo").as_posix()])
if (workspace / "camera_platform_live/vitis-comp.json").exists():
    platform = client.get_component(name="camera_platform_live")
else:
    platform = client.create_platform_component(
        name="camera_platform_live",
        hw_design=(root / "hardware/camera/build/camera_cnn.xsa").as_posix(),
        os="standalone", cpu="ps7_cortexa9_0", domain_name="camera_domain")
domain = platform.get_domain("camera_domain")
if not any(lib["name"] == "lwip220" for lib in domain.get_libs()):
    domain.set_lib(lib_name="lwip220")
domain.set_config(option="lib", lib_name="lwip220", param="lwip220_api_mode", value="RAW_API")
domain.set_config(option="lib", lib_name="lwip220", param="lwip220_dhcp", value="false")
domain.set_config(option="lib", lib_name="lwip220", param="lwip220_tcp", value="false")
platform.build()
