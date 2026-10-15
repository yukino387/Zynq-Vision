$ErrorActionPreference='Stop'
$taskCompiler='C:/AMDDesignTools/2026.1/Vivado/tps/mingw/10.0.0/win64.o/nt/bin'
$env:PATH="$taskCompiler;$env:PATH"
& 'C:/Users/YUKINO/AppData/Local/Programs/Python/Python313/python.exe' "$PSScriptRoot/prepare.py"
if($LASTEXITCODE){throw 'Test preparation failed'}
& "$taskCompiler/g++.exe" -O2 -std=c++11 -Wno-unknown-pragmas "$PSScriptRoot/loader_test.cpp" -o "$PSScriptRoot/build/loader_test.exe"
if($LASTEXITCODE){throw 'Loader test compilation failed'}
& "$PSScriptRoot/build/loader_test.exe"
if($LASTEXITCODE){throw 'Loader reference check failed'}
