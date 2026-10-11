$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBsp = Join-Path $taskRoot 'cnn_accelerator/export/cnn_accelerator/sw/standalone_ps7_cortexa9_0'
$taskBin = 'C:/AMDDesignTools/2026.1/Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin'
$taskBuild = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force $taskBuild | Out-Null
$taskFlags = @('-DSDT','-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard','-O2','-g3','-Wall','-Wextra','-Werror',"-specs=$taskBsp/Xilinx.spec", "-I$taskBsp/include", "-I$taskRoot", "-I$taskRoot/cnn_accelerator/export/cnn_accelerator/sw/standalone_ps7_cortexa9_0/hw_artifacts/drivers/conv_v1_0/src")
$taskObjects = @()
foreach ($taskSource in @("$taskRoot/camera/camera_input.cpp", "$PSScriptRoot/main.cpp")) {
    $taskObject = Join-Path $taskBuild (([IO.Path]::GetFileNameWithoutExtension($taskSource)) + '.o')
    & "$taskBin/arm-none-eabi-g++.exe" @taskFlags -std=c++11 -c $taskSource -o $taskObject
    if ($LASTEXITCODE) { throw 'Camera test compilation failed' }
    $taskObjects += $taskObject
}
& "$taskBin/arm-none-eabi-gcc.exe" @taskFlags @taskObjects "-Wl,-T,$taskRoot/cnn_app/src/lscript.ld" "-L$taskBsp/lib" '-Wl,--start-group' '-lxilstandalone' '-lxiltimer' '-lxil' '-lstdc++' '-lgcc' '-lc' '-lm' '-Wl,--end-group' -o "$taskBuild/camera_test.elf"
if ($LASTEXITCODE) { throw 'Camera test linking failed' }
& "$taskBin/arm-none-eabi-size.exe" "$taskBuild/camera_test.elf"
$taskAddresses = @('set addresses [dict create]')
& "$taskBin/arm-none-eabi-nm.exe" "$taskBuild/camera_test.elf" | ForEach-Object {
    if ($_ -match '^([0-9a-fA-F]+)\s+\w\s+(camera_pixels|camera_input)$') {
        $taskAddresses += "dict set addresses $($Matches[2]) 0x$($Matches[1])"
    }
}
Set-Content -LiteralPath "$taskBuild/addresses.tcl" -Value $taskAddresses -Encoding ascii
