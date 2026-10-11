param([switch]$Live)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBsp = Join-Path $taskRoot 'camera/build/workspace/camera_platform_live/export/camera_platform_live/sw/camera_domain'
$taskDriver = Join-Path $taskBsp 'hw_artifacts/drivers/conv_v1_0/src'
$taskBin = 'C:/AMDDesignTools/2026.1/Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin'
$taskBuild = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force $taskBuild | Out-Null
Copy-Item -LiteralPath (Join-Path $taskRoot 'temporary/full_weight_test/expected.h') -Destination (Join-Path $PSScriptRoot 'expected.h')
$taskFlags = @('-DSDT','-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard','-O2','-g3','-Wall','-Wextra', "-specs=$taskBsp/Xilinx.spec", "-I$taskBsp/include", "-I$taskDriver", "-I$taskRoot")
& "$taskBin/arm-none-eabi-gcc.exe" @taskFlags -c "$taskDriver/xconv.c" -o "$taskBuild/xconv.o"
if ($LASTEXITCODE) { throw 'Conv driver compilation failed' }
$taskObjects = @("$taskBuild/xconv.o")
$taskSources = @('basic_op.cpp','basic_conv.cpp','basic_conv_weight.cpp','resblock_body.cpp','resblock_body_weight.cpp','cspdarknet.cpp','cspdarknet_weight.cpp','yolo4_tiny.cpp','yolo4_tiny_weight.cpp','camera/camera_input.cpp','camera/udp_output.cpp')
$taskEntry = if ($Live) { 'live_main.cpp' } else { 'main.cpp' }
foreach ($taskSource in $taskSources + @("temporary/camera_inference_test/$taskEntry")) {
    $taskObject = Join-Path $taskBuild (([IO.Path]::GetFileNameWithoutExtension($taskSource)) + '.o')
    $taskWarnings = @('-Werror')
    if ($taskSource -eq 'basic_op.cpp') { $taskWarnings = @() }
    & "$taskBin/arm-none-eabi-g++.exe" @taskFlags @taskWarnings -std=c++11 -c (Join-Path $taskRoot $taskSource) -o $taskObject
    if ($LASTEXITCODE) { throw "$taskSource compilation failed" }
    $taskObjects += $taskObject
}
$taskName = if ($Live) { 'camera_live' } else { 'camera_inference_test' }
& "$taskBin/arm-none-eabi-gcc.exe" @taskFlags @taskObjects '-Wl,--defsym,_HEAP_SIZE=0x4000000' '-Wl,--defsym,_STACK_SIZE=0x10000' "-Wl,-T,$taskRoot/cnn_app/src/lscript.ld" "-L$taskBsp/lib" '-Wl,--start-group' '-llwip220' '-lxilstandalone' '-lxiltimer' '-lxil' '-lstdc++' '-lgcc' '-lc' '-lm' '-Wl,--end-group' -o "$taskBuild/$taskName.elf"
if ($LASTEXITCODE) { throw 'Camera inference linking failed' }
& "$taskBin/arm-none-eabi-size.exe" "$taskBuild/$taskName.elf"
$taskAddresses = @('set addresses [dict create]')
& "$taskBin/arm-none-eabi-nm.exe" "$taskBuild/$taskName.elf" | ForEach-Object {
    if ($_ -match '^([0-9a-fA-F]+)\s+\w\s+(raw_files|pc_directory|pixels|out0_storage|out1_storage)$') {
        $taskAddresses += "dict set addresses $($Matches[2]) 0x$($Matches[1])"
    }
}
if ($taskAddresses.Count -ne 6) { throw 'Test symbols missing' }
Set-Content -LiteralPath "$taskBuild/$taskName-addresses.tcl" -Value $taskAddresses -Encoding ascii
