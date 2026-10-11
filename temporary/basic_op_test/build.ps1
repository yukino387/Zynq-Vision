$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$taskBsp = Join-Path $taskRoot 'cnn_accelerator\export\cnn_accelerator\sw\standalone_ps7_cortexa9_0'
$taskDriver = Join-Path $taskBsp 'hw_artifacts\drivers\conv_v1_0\src'
$taskBin = 'C:\AMDDesignTools\2026.1\Vitis\gnu\aarch32\nt\gcc-arm-none-eabi\bin'
$taskBuild = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
$taskFlags = @('-DSDT', '-mcpu=cortex-a9', '-mfpu=vfpv3', '-mfloat-abi=hard', '-O0', '-g3', '-Wall', '-Wextra', "-specs=$taskBsp\Xilinx.spec", "-I$taskBsp\include", "-I$taskDriver", "-I$taskRoot")
& "$taskBin\arm-none-eabi-gcc.exe" @taskFlags -c "$taskDriver\xconv.c" -o "$taskBuild\xconv.o"
if ($LASTEXITCODE) { throw 'Driver compilation failed' }
& "$taskBin\arm-none-eabi-g++.exe" @taskFlags -std=c++11 -c "$taskRoot\basic_op.cpp" -o "$taskBuild\basic_op.o"
if ($LASTEXITCODE) { throw 'basic_op compilation failed' }
& "$taskBin\arm-none-eabi-g++.exe" @taskFlags -std=c++11 -Werror -c "$PSScriptRoot\main.cpp" -o "$taskBuild\main.o"
if ($LASTEXITCODE) { throw 'Test compilation failed' }
& "$taskBin\arm-none-eabi-gcc.exe" @taskFlags "$taskBuild\main.o" "$taskBuild\basic_op.o" "$taskBuild\xconv.o" "-Wl,-T,$taskRoot\cnn_app\src\lscript.ld" "-L$taskBsp\lib" '-Wl,--start-group' '-lxilstandalone' '-lxiltimer' '-lxil' '-lgcc' '-lc' '-Wl,--end-group' "-Wl,-Map,$taskBuild\basic_op_test.map" -o "$taskBuild\basic_op_test.elf"
if ($LASTEXITCODE) { throw 'Test linking failed' }
& "$taskBin\arm-none-eabi-size.exe" "$taskBuild\basic_op_test.elf"
