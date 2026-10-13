from pathlib import Path
import atexit
import re
import shutil
import sys
import vitis
import build_pb2

root = Path(__file__).resolve().parents[1]
workspace = root / "vitis_live"
workspace.mkdir(exist_ok=True)
atexit.unregister(vitis.dispose)
client = vitis.create_client(port=int(sys.argv[1]))
current_workspace = client.get_workspace()
if not current_workspace:
    client.set_workspace(workspace.as_posix())
elif Path(current_workspace).resolve() != workspace.resolve():
    raise RuntimeError('Vitis server is using a different workspace')
library = root / "camera/build/lwip_repo/lwip220_v1_4"
if not library.exists():
    shutil.copytree("C:/AMDDesignTools/2026.1/Vitis/data/embeddedsw/ThirdParty/sw_services/lwip220_v1_4", library)
schema = library / "data/lwip220.yaml"
schema.chmod(0o666)
schema.write_text(schema.read_text(encoding="utf-8-sig"), encoding="utf-8")
client.set_embedded_sw_repo(level="LOCAL", path=["C:/AMDDesignTools/2026.1/Vitis/data/embeddedsw",
    (root / "camera/build/lwip_repo").as_posix()])
if not (workspace / "camera_platform_live/vitis-comp.json").exists():
    platform_component = client.create_platform_component(name="camera_platform_live",
        hw_design=(root / "hardware/camera/build/camera_cnn.xsa").as_posix(),
        os="standalone", cpu="ps7_cortexa9_0", domain_name="camera_domain")
else:
    platform_component = client.get_component(name="camera_platform_live")
    platform_component.update_hw(hw_design=(root / "hardware/camera/build/camera_cnn.xsa").as_posix())
domain = platform_component.get_domain("camera_domain")
domain.set_lib(lib_name="lwip220")
domain.set_config(option="lib", lib_name="lwip220", param="lwip220_api_mode", value="RAW_API")
domain.set_config(option="lib", lib_name="lwip220", param="lwip220_dhcp", value="false")
domain.set_config(option="lib", lib_name="lwip220", param="lwip220_tcp", value="false")
if platform_component.build() != build_pb2.BuildResponse.SUCCESS:
    raise RuntimeError("Platform build failed")
if not (workspace / "camera_platform_live/export/camera_platform_live/sw/camera_domain/include/lwip/init.h").exists():
    raise RuntimeError("The platform is missing lwIP headers")
platform = workspace / "camera_platform_live/export/camera_platform_live/camera_platform_live.xpfm"
client.add_platform_repos(platform=platform.parent.as_posix())
if (workspace / "camera_live/vitis-comp.json").exists():
    app = client.get_component(name="camera_live")
else:
    app = client.create_app_component(name="camera_live", platform=platform.as_posix(),
                                      domain="camera_domain", template="empty_application")
app.import_files(from_loc=(root / "camera").as_posix(),
                 files=["camera_input.cpp", "camera_input.h", "udp_output.cpp", "udp_output.h"],
                 is_skip_copy_sources=True)
app.import_files(from_loc=(root / "camera/int8").as_posix(),
                 files=["live_main.cpp", "gray.cpp", "gray.h", "gray_coefficients.h", "model.h", "weights.S"],
                 is_skip_copy_sources=True)
config = workspace / "camera_live/src/UserConfig.cmake"
bsp = workspace / "camera_platform_live/export/camera_platform_live/sw/camera_domain"
driver = bsp / "hw_artifacts/drivers/conv_v1_0/src"
app.import_files(from_loc=driver.as_posix(), files=["xconv.c", "xconv.h", "xconv_hw.h"],
                 is_skip_copy_sources=True)
text = config.read_text(encoding="utf-8")
settings = {
    "USER_INCLUDE_DIRECTORIES": f'"{root.as_posix()}" "{driver.as_posix()}"',
    "USER_COMPILE_OPTIMIZATION_LEVEL": "-O2",
    "USER_COMPILE_OTHER_FLAGS": "-mfpu=neon",
    "USER_COMPILE_SOURCES": "\n" + "\n".join(f'"{path.as_posix()}"' for path in [
        driver / "xconv.c", root / "camera/int8/live_main.cpp", root / "camera/int8/gray.cpp",
        root / "camera/int8/weights.S", root / "camera/camera_input.cpp", root / "camera/udp_output.cpp"]),
    "USER_COMPILE_DEFINITIONS": "SDT",
    "USER_LINK_OTHER_FLAGS": '"-Wl,--defsym,_HEAP_SIZE=0x100000 -Wl,--defsym,_STACK_SIZE=0x10000"',
    "USER_LINKER_SCRIPT": '"${CMAKE_SOURCE_DIR}/lscript.ld"',
}
for name, value in settings.items():
    text, replacements = re.subn(r"set\(" + name + r"\s+[^)]*\)", f"set({name} {value})", text, count=1)
    if replacements != 1:
        raise RuntimeError(f"Missing Vitis setting: {name}")
config.write_text(text, encoding="utf-8")
if app.build() != build_pb2.BuildResponse.SUCCESS:
    raise RuntimeError("Vitis application build failed")
if not (workspace / "camera_live/build/camera_live.elf").exists():
    raise RuntimeError("Vitis did not produce camera_live.elf")
print(workspace / "camera_live/build/camera_live.elf")
