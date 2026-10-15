New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot "build") | Out-Null
@'
#define camera_init camera_init_normal
#include "../../../camera/camera_input.cpp"
#undef camera_init
bool camera_init(){
    if(!camera_init_normal())return false;
    uint8_t awb=0;
    return read_register(0x3406,awb) && write_register(0x3406,awb|1) && write_register(0x3503,3) && write_register(0x503d,0x80);
}
'@ | Set-Content -Encoding ascii (Join-Path $PSScriptRoot 'build/camera_colorbar.cpp')
$Target='live'
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBsp = Join-Path $taskRoot 'vitis_live/camera_platform_live/export/camera_platform_live/sw/camera_domain'
$taskDriver = Join-Path $taskBsp 'hw_artifacts/drivers/conv_v1_0/src'
$taskBin = 'C:/AMDDesignTools/2026.1/Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin'
$taskBuild = Join-Path $PSScriptRoot "build/$Target"
New-Item -ItemType Directory -Force $taskBuild | Out-Null
$taskFlags = @('-DSDT', '-mcpu=cortex-a9', '-mfpu=neon', '-mfloat-abi=hard', '-O2', '-g3',
    "-specs=$taskBsp/Xilinx.spec", "-I$taskBsp/include", "-I$taskDriver", "-I$taskRoot")
& "$taskBin/arm-none-eabi-gcc.exe" @taskFlags -c "$taskDriver/xconv.c" -o "$taskBuild/xconv.o"
if ($LASTEXITCODE) { throw 'Driver compilation failed' }
$taskMain=if($Target -eq 'live') {"$taskRoot/camera/int8/live_main.cpp"} else {"$PSScriptRoot/board.cpp"}
& "$taskBin/arm-none-eabi-g++.exe" @taskFlags -std=c++11 -c $taskMain -o "$taskBuild/board.o"
if ($LASTEXITCODE) { throw 'Test compilation failed' }
$taskGray="$taskRoot/camera/int8/gray.cpp"
& "$taskBin/arm-none-eabi-g++.exe" @taskFlags -std=c++11 -c $taskGray -o "$taskBuild/gray.o"
if ($LASTEXITCODE) { throw 'Preprocessing compilation failed' }
$taskObjects=@("$taskBuild/xconv.o","$taskBuild/board.o","$taskBuild/gray.o")
if($Target -eq 'live') {
    & "$taskBin/arm-none-eabi-gcc.exe" @taskFlags -c "$taskRoot/camera/int8/weights.S" -o "$taskBuild/weights.o"
    if($LASTEXITCODE) { throw 'Embedded weight assembly failed' }
    $taskObjects+="$taskBuild/weights.o"
    foreach($taskName in @('camera_input','udp_output')) {
        $taskSource=if($taskName -eq 'camera_input') {"$PSScriptRoot/build/camera_colorbar.cpp"} else {"$taskRoot/camera/$taskName.cpp"}
        & "$taskBin/arm-none-eabi-g++.exe" @taskFlags -std=c++11 -c $taskSource -o "$taskBuild/$taskName.o"
        if($LASTEXITCODE) { throw "$taskName compilation failed" }
        $taskObjects+="$taskBuild/$taskName.o"
    }
}
& "$taskBin/arm-none-eabi-gcc.exe" @taskFlags @taskObjects '-Wl,--defsym,_HEAP_SIZE=0x100000' '-Wl,--defsym,_STACK_SIZE=0x10000' "-Wl,-T,$taskRoot/cnn_app/src/lscript.ld" "-L$taskBsp/lib" '-Wl,--start-group' '-llwip220' '-lxilstandalone' '-lxiltimer' '-lxil' '-lstdc++' '-lgcc' '-lc' '-lm' '-Wl,--end-group' -o "$taskBuild/test.elf"
if ($LASTEXITCODE) { throw 'Test linking failed' }
if($Target -eq 'live') { return }
$taskAddresses = @('set addresses [dict create]')
& "$taskBin/arm-none-eabi-nm.exe" "$taskBuild/test.elf" | ForEach-Object {
    if ($_ -match '^([0-9a-fA-F]+)\s+\w\s+(features|weights|metadata|gray_pixels|forward_us|layer_us|out0|out1)$') {
        $taskAddresses += "dict set addresses $($Matches[2]) 0x$($Matches[1])"
    }
}
$taskExpectedCount=if($Target -eq 'board') {9} else {4}
if ($taskAddresses.Count -ne $taskExpectedCount) { throw 'Staging symbols missing' }
Set-Content "$taskBuild/addresses.tcl" $taskAddresses -Encoding ascii
