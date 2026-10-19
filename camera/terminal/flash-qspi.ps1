$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$delivery = Join-Path $PSScriptRoot 'build/delivery'
$boot = Join-Path $delivery 'boot/BOOT.bin'
$entry = (Get-Content (Join-Path $delivery 'checksums.json') -Raw | ConvertFrom-Json).files | Where-Object { $_.path -eq 'boot/BOOT.bin' }
$size = (Get-Item -LiteralPath $boot).Length
$hash = (Get-FileHash -LiteralPath $boot -Algorithm SHA256).Hash.ToLowerInvariant()
if (!$entry -or $size -ne $entry.size -or $hash -ne $entry.sha256) { throw 'BOOT.bin differs from the qualified delivery manifest' }
if ($size -ge 0x007FE000) { throw 'Terminal boot image overlaps the existing firmware records' }
. (Join-Path $root 'hardware/camera/vivado_env.ps1')
$vitisRoot = 'C:/AMDDesignTools/2026.1/Vitis'
$env:XILINX_VITIS = $vitisRoot
$env:RDI_APPROOT = $vitisRoot
$env:HDI_APPROOT = $vitisRoot
$env:RDI_DATADIR = "$vitisRoot/data"
$env:RDI_LIBDIR = "$vitisRoot/lib/win64.o"
$env:RDI_BINDIR = "$vitisRoot/bin"
$env:PATH = "$env:RDI_LIBDIR;$vitisRoot/bin;$env:PATH"
$bsp = Join-Path $PSScriptRoot 'build/vitis/vision_terminal_platform/export/vision_terminal_platform/sw/terminal_boot'
$directory = Join-Path $PSScriptRoot 'build/qspi-backups'
New-Item -ItemType Directory -Force $directory | Out-Null
$helper = Join-Path $directory 'qspi_program.elf'
& "$vitisRoot/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-g++.exe" -DSDT -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -O2 "-I$bsp/include" "-I$root/camera" "-specs=$bsp/Xilinx.spec" '-Wl,-u,_close,-u,_lseek,-u,_read,-u,_write,-u,_sbrk' '-Wl,--defsym,_HEAP_SIZE=0x100000' '-Wl,--defsym,_STACK_SIZE=0x10000' -T (Join-Path $root 'vitis_live/camera_live/src/lscript.ld') (Join-Path $root 'camera/qspi_program.cpp') "-L$bsp/lib" '-Wl,--start-group' -lxilstandalone -lxiltimer -lxil -lgcc -lc -lstdc++ '-Wl,--end-group' -o $helper
if ($LASTEXITCODE) { throw 'QSPI helper compilation failed' }
$backup = Join-Path $directory ('flash-before-terminal-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bin')
& "$vitisRoot/bin/unwrapped/win64.o/xsdb.exe" (Join-Path $PSScriptRoot 'program_qspi.tcl') $root $helper $boot $backup $size $hash
if ($LASTEXITCODE) { throw 'QSPI programming/readback verification failed; preserve the backup and inspect the output' }
$result = @{ bootBytes=$size; bootSha256=$hash; jedec='ef4019'; flashCapacityBytes=33554432; backup=$backup; backupSha256=(Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToLowerInvariant(); bootVerified=$false }
$result | ConvertTo-Json | Set-Content -LiteralPath ($backup + '.json') -Encoding utf8
Write-Output ('QSPI_VERIFICATION=' + ($result | ConvertTo-Json -Compress))
Write-Output 'QSPI verified. Power cycle the board to verify autonomous boot.'
