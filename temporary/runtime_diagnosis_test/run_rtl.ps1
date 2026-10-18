$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. "$taskRoot/hardware/camera/vivado_env.ps1"
& 'C:/Users/YUKINO/AppData/Local/Programs/Python/Python313/python.exe' "$PSScriptRoot/offline_rtl.py"
if($LASTEXITCODE) { throw 'Test generation failed' }
Push-Location "$PSScriptRoot/build/rtl"
try {
    & "$env:XILINX_VIVADO/bin/xvlog.bat" -prj sources.prj *> compile.log
    if($LASTEXITCODE) { throw 'RTL compilation failed; see compile.log' }
    & "$env:XILINX_VIVADO/bin/xelab.bat" work.tb -s diagnosis -mt 4 *> elaborate.log
    if($LASTEXITCODE) { throw 'RTL elaboration failed; see elaborate.log' }
    & "$env:XILINX_VIVADO/bin/xsim.bat" diagnosis -tclbatch run.tcl *> simulation.log
    if($LASTEXITCODE) { throw 'RTL simulation failed; see simulation.log' }
    if(-not (Select-String -LiteralPath simulation.log -SimpleMatch 'OFFLINE RTL PASS' -Quiet)) { throw 'Simulation did not pass' }
    Select-String -LiteralPath simulation.log -Pattern '^PROBE |OFFLINE RTL PASS' | ForEach-Object { $_.Line }
} finally { Pop-Location }
