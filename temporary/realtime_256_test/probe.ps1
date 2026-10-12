$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBsp=Join-Path $taskRoot 'vitis_live/camera_platform_live/export/camera_platform_live/sw/camera_domain'
$taskCompiler='C:/AMDDesignTools/2026.1/Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-g++.exe'
& $taskCompiler -DSDT -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -O2 -g3 "-I$taskBsp/include" "-I$taskRoot" -c "$PSScriptRoot/camera_probe.cpp" -o "$PSScriptRoot/build/camera_probe.o"
if($LASTEXITCODE){throw 'Camera probe compilation failed'}
& ($taskCompiler.Replace('g++.exe','gcc.exe')) -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard "-specs=$taskBsp/Xilinx.spec" "$PSScriptRoot/build/camera_probe.o" "-Wl,-T,$taskRoot/vitis_live/camera_live/src/lscript.ld" "-L$taskBsp/lib" '-Wl,--start-group' -lxilstandalone -lxiltimer -lxil -lstdc++ -lgcc -lc -lm '-Wl,--end-group' -o "$PSScriptRoot/build/camera_probe.elf"
if($LASTEXITCODE){throw 'Camera probe build failed'}
. "$taskRoot/hardware/camera/vivado_env.ps1"
& 'C:/AMDDesignTools/2026.1/Vitis/bin/xsdb.bat' "$PSScriptRoot/probe.tcl"
if($LASTEXITCODE){throw 'Camera probe run failed'}
