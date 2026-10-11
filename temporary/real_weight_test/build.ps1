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
& "$taskBin\arm-none-eabi-g++.exe" @taskFlags -std=c++11 -Werror -c "$taskRoot\basic_conv.cpp" -o "$taskBuild\basic_conv.o"
if ($LASTEXITCODE) { throw 'BasicConv compilation failed' }
& "$taskBin\arm-none-eabi-g++.exe" @taskFlags -std=c++11 -Werror -c "$taskRoot\basic_conv_weight.cpp" -o "$taskBuild\basic_conv_weight.o"
if ($LASTEXITCODE) { throw 'Weight loader compilation failed' }
& "$taskBin\arm-none-eabi-g++.exe" @taskFlags -std=c++11 -Werror -c "$PSScriptRoot\main.cpp" -o "$taskBuild\main.o"
if ($LASTEXITCODE) { throw 'Test compilation failed' }
& "$taskBin\arm-none-eabi-gcc.exe" @taskFlags "$taskBuild\main.o" "$taskBuild\basic_conv_weight.o" "$taskBuild\basic_conv.o" "$taskBuild\basic_op.o" "$taskBuild\xconv.o" '-Wl,--defsym,_HEAP_SIZE=0x20000' "-Wl,-T,$taskRoot\cnn_app\src\lscript.ld" "-L$taskBsp\lib" '-Wl,--start-group' '-lxilstandalone' '-lxiltimer' '-lxil' '-lstdc++' '-lgcc' '-lc' '-lm' '-Wl,--end-group' "-Wl,-Map,$taskBuild\real_weight_test.map" -o "$taskBuild\real_weight_test.elf"
if ($LASTEXITCODE) { throw 'Test linking failed' }
& "$taskBin\arm-none-eabi-size.exe" "$taskBuild\real_weight_test.elf"
$taskAddressLines = @('set addresses [dict create]')
& "$taskBin\arm-none-eabi-nm.exe" "$taskBuild\real_weight_test.elf" | ForEach-Object {
    if ($_ -match '^([0-9a-fA-F]+)\s+\w\s+(raw_weight|raw_bias|pc_directory)$') {
        $taskAddressLines += "dict set addresses $($Matches[2]) 0x$($Matches[1])"
    }
}
if ($taskAddressLines.Count -ne 4) { throw 'Staging symbols not found' }
Set-Content -LiteralPath "$taskBuild\addresses.tcl" -Value $taskAddressLines -Encoding ascii
