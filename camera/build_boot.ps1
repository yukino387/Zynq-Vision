param([switch]$Flash)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $taskRoot 'hardware/camera/vivado_env.ps1')
$env:XILINX_VITIS = 'C:/AMDDesignTools/2026.1/Vitis'
$env:RDI_APPROOT = $env:XILINX_VITIS
$env:HDI_APPROOT = $env:XILINX_VITIS
$env:RDI_DATADIR = "$env:XILINX_VITIS/data"
$env:RDI_LIBDIR = "$env:XILINX_VITIS/lib/win64.o"
$env:RDI_BINDIR = "$env:XILINX_VITIS/bin"
$env:PATH = "$env:RDI_LIBDIR;$env:XILINX_VITIS/bin;$env:PATH"
$bootDir = Join-Path $PSScriptRoot 'build/boot'
New-Item -ItemType Directory -Force $bootDir | Out-Null
$fsbl = Join-Path $taskRoot 'vitis_live/camera_platform_live/zynq_fsbl/build/fsbl.elf'
# Platform updates can leave stale PS initialization sources in the FSBL.
$fsblSource = Join-Path $taskRoot 'vitis_live/camera_platform_live/zynq_fsbl'
foreach ($name in @('ps7_init.c','ps7_init.h')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot "vitis_live/camera_platform_live/export/camera_platform_live/hw/sdt/$name") -Destination (Join-Path $fsblSource $name) -Force
    (Get-Item -LiteralPath (Join-Path $fsblSource $name)).LastWriteTime = Get-Date
}
$env:PATH = "$env:XILINX_VITIS/gnu/aarch32/nt/gcc-arm-none-eabi/bin;$env:PATH"
& "$env:XILINX_VITIS/tps/win64/cmake-4.0.1/bin/cmake.exe" --build (Join-Path $fsblSource 'build') --parallel 8
if ($LASTEXITCODE) { throw 'FSBL rebuild failed' }
$bit = Join-Path $taskRoot 'hardware/camera/build/system_wrapper.bit'
$app = Join-Path $taskRoot 'vitis_live/camera_live/build/camera_live.elf'
foreach ($artifact in @($fsbl,$bit,$app)) { if (-not (Test-Path -LiteralPath $artifact)) { throw "Missing artifact: $artifact" } }
$bif = Join-Path $bootDir 'boot.bif'
$boot = Join-Path $bootDir 'BOOT.bin'
@"
zynq_sd_model:
{
    [bootloader] $($fsbl.Replace('\','/'))
    $($bit.Replace('\','/'))
    $($app.Replace('\','/'))
}
"@ | Set-Content -LiteralPath $bif -Encoding ascii
& "$env:XILINX_VITIS/bin/unwrapped/win64.o/bootgen.exe" -arch zynq -image $bif -o $boot -w on
if ($LASTEXITCODE) { throw 'Bootgen failed' }
$bootSize = (Get-Item -LiteralPath $boot).Length
if ($bootSize -ge 0x007FE000) { throw 'Boot image must stay below the firmware records (0x007FE000)' }
$hash = (Get-FileHash -LiteralPath $boot -Algorithm SHA256).Hash
Write-Output "BOOT.bin bytes=$bootSize SHA256=$hash"
if ($Flash) {
    $bsp = Join-Path $taskRoot 'vitis_live/camera_platform_live/export/camera_platform_live/sw/camera_domain'
    $helper = Join-Path $bootDir 'qspi_program.elf'
    & "$env:XILINX_VITIS/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-g++.exe" -DSDT -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -O2 -g "-I$bsp/include" "-I$PSScriptRoot" "-specs=$bsp/Xilinx.spec" '-Wl,-u,_close,-u,_lseek,-u,_read,-u,_write,-u,_sbrk' '-Wl,--defsym,_HEAP_SIZE=0x100000' '-Wl,--defsym,_STACK_SIZE=0x10000' -T (Join-Path $taskRoot 'vitis_live/camera_live/src/lscript.ld') (Join-Path $PSScriptRoot 'qspi_program.cpp') "-L$bsp/lib" '-Wl,--start-group' -lxilstandalone -lxiltimer -lxil -lgcc -lc -lstdc++ '-Wl,--end-group' -o $helper
    if ($LASTEXITCODE) { throw 'QSPI helper compilation failed' }
    $backup = Join-Path $bootDir ("flash-backup-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bin')
    & "$env:XILINX_VITIS/bin/unwrapped/win64.o/xsdb.exe" (Join-Path $PSScriptRoot 'program_qspi.tcl') $taskRoot $helper $boot $backup $bootSize $hash
    if ($LASTEXITCODE) { throw 'QSPI programming or full readback verification failed' }
}
