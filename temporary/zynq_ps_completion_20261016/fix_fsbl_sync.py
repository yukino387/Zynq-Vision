from pathlib import Path
p=Path('camera/create_app.py')
s=p.read_text(encoding='utf-8')
needle='if not (workspace / "camera_platform_live/export/camera_platform_live/sw/camera_domain/include/lwip/init.h").exists():'
insert='''# Updating the platform does not refresh the generated FSBL source copies.
fsbl_dir = workspace / "camera_platform_live/zynq_fsbl"
for filename in ("ps7_init.c", "ps7_init.h"):
    shutil.copyfile(workspace / "camera_platform_live/export/camera_platform_live/hw/sdt" / filename,
                    fsbl_dir / filename)
if platform_component.build() != build_pb2.BuildResponse.SUCCESS:
    raise RuntimeError("FSBL rebuild with current PS initialization failed")
'''
assert needle in s;s=s.replace(needle,insert+needle);p.write_bytes(s.encode())
p=Path('camera/build_boot.ps1');s=p.read_text(encoding='utf-8');needle="$bit = Join-Path $taskRoot 'hardware/camera/build/system_wrapper.bit'"
insert='''# Platform updates can leave stale PS initialization sources in the FSBL.
$fsblSource = Join-Path $taskRoot 'vitis_live/camera_platform_live/zynq_fsbl'
foreach ($name in @('ps7_init.c','ps7_init.h')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot "vitis_live/camera_platform_live/export/camera_platform_live/hw/sdt/$name") -Destination (Join-Path $fsblSource $name) -Force
}
$env:PATH = "$env:XILINX_VITIS/gnu/aarch32/nt/gcc-arm-none-eabi/bin;$env:PATH"
& "$env:XILINX_VITIS/tps/win64/cmake-4.0.1/bin/cmake.exe" --build (Join-Path $fsblSource 'build') --parallel 8
if ($LASTEXITCODE) { throw 'FSBL rebuild failed' }
'''
assert needle in s;s=s.replace(needle,insert+needle);p.write_bytes(s.encode())
