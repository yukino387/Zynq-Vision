$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBsp = Join-Path $taskRoot 'vitis_live/camera_platform_live/export/camera_platform_live/sw/camera_domain'
$taskDriver = Join-Path $taskBsp 'hw_artifacts/drivers/conv_v1_0/src'
$taskBin = 'C:/AMDDesignTools/2026.1/Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin'
$taskBuild = Join-Path $PSScriptRoot 'build/fixed_image'
New-Item -ItemType Directory -Force $taskBuild | Out-Null
$taskFlags = @('-DSDT', '-mcpu=cortex-a9', '-mfpu=vfpv3', '-mfloat-abi=hard', '-O2', '-g3',
    "-specs=$taskBsp/Xilinx.spec", "-I$taskBsp/include", "-I$taskDriver", "-I$taskRoot")
& "$taskBin/arm-none-eabi-gcc.exe" @taskFlags -c "$taskDriver/xconv.c" -o "$taskBuild/xconv.o"
if ($LASTEXITCODE) { throw 'Conv driver compilation failed' }
$taskObjects = @("$taskBuild/xconv.o")
foreach ($taskName in @('basic_op', 'basic_conv', 'basic_conv_weight', 'resblock_body',
    'resblock_body_weight', 'cspdarknet', 'cspdarknet_weight', 'yolo4_tiny', 'yolo4_tiny_weight', 'main')) {
    $taskSource = Join-Path $taskRoot "$taskName.cpp"
    if ($taskName -eq 'main') { $taskSource = Join-Path $taskRoot 'temporary/image_inference_test/main.cpp' }
    $taskObject = Join-Path $taskBuild "$taskName.o"
    & "$taskBin/arm-none-eabi-g++.exe" @taskFlags -std=c++11 -c $taskSource -o $taskObject
    if ($LASTEXITCODE) { throw "$taskName compilation failed" }
    $taskObjects += $taskObject
}
& "$taskBin/arm-none-eabi-gcc.exe" @taskFlags @taskObjects '-Wl,--defsym,_HEAP_SIZE=0x4000000' '-Wl,--defsym,_STACK_SIZE=0x10000' "-Wl,-T,$taskRoot/cnn_app/src/lscript.ld" "-L$taskBsp/lib" '-Wl,--start-group' '-lxilstandalone' '-lxiltimer' '-lxil' '-lstdc++' '-lgcc' '-lc' '-lm' '-Wl,--end-group' -o "$taskBuild/fixed_image.elf"
if ($LASTEXITCODE) { throw 'Fixed-image test linking failed' }
& "$taskBin/arm-none-eabi-size.exe" "$taskBuild/fixed_image.elf"
$taskAddresses = @('set addresses [dict create]')
& "$taskBin/arm-none-eabi-nm.exe" "$taskBuild/fixed_image.elf" | ForEach-Object {
    if ($_ -match '^([0-9a-fA-F]+)\s+\w\s+(raw_files|pc_directory|input_data|out0_storage|out1_storage)$') {
        $taskAddresses += "dict set addresses $($Matches[2]) 0x$($Matches[1])"
    }
}
if ($taskAddresses.Count -ne 6) { throw 'Fixed-image staging symbols missing' }
Set-Content "$taskBuild/addresses.tcl" $taskAddresses -Encoding ascii
