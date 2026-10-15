$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBsp=Join-Path $taskRoot 'vitis_live/camera_platform_live/export/camera_platform_live/sw/camera_domain'
$taskBin='C:/AMDDesignTools/2026.1/Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin'
$taskBuild=Join-Path $PSScriptRoot 'build'
$taskFlags=@('-DSDT','-mcpu=cortex-a9','-mfpu=neon','-mfloat-abi=hard','-O2','-g3',"-specs=$taskBsp/Xilinx.spec","-I$taskBsp/include","-I$taskRoot")
& "$taskBin/arm-none-eabi-g++.exe" @taskFlags -std=c++11 -c "$PSScriptRoot/probe.cpp" -o "$taskBuild/probe.o"
if($LASTEXITCODE){throw 'Probe compilation failed'}
& "$taskBin/arm-none-eabi-gcc.exe" @taskFlags "$taskBuild/probe.o" '-Wl,--defsym,_HEAP_SIZE=0x100000' '-Wl,--defsym,_STACK_SIZE=0x10000' "-Wl,-T,$taskRoot/cnn_app/src/lscript.ld" "-L$taskBsp/lib" '-Wl,--start-group' '-lxilstandalone' '-lxiltimer' '-lxil' '-lstdc++' '-lgcc' '-lc' '-lm' '-Wl,--end-group' -o "$taskBuild/probe.elf"
if($LASTEXITCODE){throw 'Probe linking failed'}
