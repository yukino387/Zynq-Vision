$ErrorActionPreference = 'Stop'
$amdRoot = if ($env:AMD_TOOLS_ROOT) { $env:AMD_TOOLS_ROOT } else { 'C:/AMDDesignTools/2026.1' }
$cmake = Join-Path $amdRoot 'Vitis/tps/win64/cmake-4.0.1/bin/cmake.exe'
$make = Join-Path $amdRoot 'Vitis/tps/mingw/10.0.0/win64.o/nt/bin/mingw32-make.exe'
$output = Join-Path $PSScriptRoot 'build/arm'
& (Join-Path $PSScriptRoot 'prepare_deps.ps1')
& $cmake -S $PSScriptRoot -B $output -G 'MinGW Makefiles' "-DCMAKE_MAKE_PROGRAM=$make" "-DCMAKE_TOOLCHAIN_FILE=$PSScriptRoot/toolchains/amd-arm-linux.cmake" -DCMAKE_BUILD_TYPE=Release
if ($LASTEXITCODE) { throw 'Terminal configure failed' }
& $cmake --build $output --parallel 8
if ($LASTEXITCODE) { throw 'Terminal build failed' }
