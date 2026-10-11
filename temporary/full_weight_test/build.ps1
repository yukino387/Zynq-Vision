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
$taskObjects = @("$taskBuild\xconv.o")
foreach ($taskName in @('basic_op','basic_conv','basic_conv_weight','resblock_body','resblock_body_weight','cspdarknet','cspdarknet_weight','yolo4_tiny','yolo4_tiny_weight','main')) {
    $taskSource = Join-Path $taskRoot "$taskName.cpp"
    if ($taskName -eq 'main') { $taskSource = Join-Path $PSScriptRoot 'main.cpp' }
    $taskWarnings = @('-Werror')
    if ($taskName -eq 'basic_op') { $taskWarnings = @() }
    & "$taskBin\arm-none-eabi-g++.exe" @taskFlags @taskWarnings -std=c++11 -c $taskSource -o "$taskBuild\$taskName.o"
    if ($LASTEXITCODE) { throw "$taskName compilation failed" }
    $taskObjects += "$taskBuild\$taskName.o"
}
& "$taskBin\arm-none-eabi-gcc.exe" @taskFlags @taskObjects '-Wl,--defsym,_HEAP_SIZE=0x4000000' '-Wl,--defsym,_STACK_SIZE=0x10000' "-Wl,-T,$taskRoot\cnn_app\src\lscript.ld" "-L$taskBsp\lib" '-Wl,--start-group' '-lxilstandalone' '-lxiltimer' '-lxil' '-lstdc++' '-lgcc' '-lc' '-lm' '-Wl,--end-group' "-Wl,-Map,$taskBuild\full_weight_test.map" -o "$taskBuild\full_weight_test.elf"
if ($LASTEXITCODE) { throw 'Test linking failed' }
& "$taskBin\arm-none-eabi-size.exe" "$taskBuild\full_weight_test.elf"
$taskAddressLines = @('set addresses [dict create]')
& "$taskBin\arm-none-eabi-nm.exe" "$taskBuild\full_weight_test.elf" | ForEach-Object {
    if ($_ -match '^([0-9a-fA-F]+)\s+\w\s+(raw_files|pc_directory)$') {
        $taskAddressLines += "dict set addresses $($Matches[2]) 0x$($Matches[1])"
    }
}
if ($taskAddressLines.Count -ne 3) { throw 'Staging symbols not found' }
Set-Content -LiteralPath "$taskBuild\addresses.tcl" -Value $taskAddressLines -Encoding ascii
