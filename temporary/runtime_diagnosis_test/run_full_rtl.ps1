$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. "$taskRoot/hardware/camera/vivado_env.ps1"
& 'C:/Users/YUKINO/AppData/Local/Programs/Python/Python313/python.exe' "$PSScriptRoot/full_rtl.py"
if($LASTEXITCODE) { throw 'Test generation failed' }
Push-Location "$PSScriptRoot/build/full_rtl"
try {
    & "$env:XILINX_VIVADO/bin/xvlog.bat" -prj sources.prj *> compile.log
    if($LASTEXITCODE) { throw 'RTL compilation failed' }
    & "$env:XILINX_VIVADO/bin/xelab.bat" work.tb -s full_diagnosis -mt 4 *> elaborate.log
    if($LASTEXITCODE) { throw 'RTL elaboration failed' }
    & "$env:XILINX_VIVADO/bin/xsim.bat" full_diagnosis -tclbatch run.tcl *> simulation.log
    if($LASTEXITCODE) { throw 'RTL simulation failed' }
    if(-not (Select-String -LiteralPath simulation.log -SimpleMatch 'WHOLE CONV RTL PASS' -Quiet)) { throw 'Simulation did not pass' }
    Select-String -LiteralPath simulation.log -Pattern '^LAYER |WHOLE CONV RTL PASS' | ForEach-Object { $_.Line }
} finally { Pop-Location }
