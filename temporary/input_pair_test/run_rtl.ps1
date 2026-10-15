param([ValidateSet('baseline','candidate')][string]$Version='candidate')
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../../hardware/camera/vivado_env.ps1')
& 'C:/Users/YUKINO/AppData/Local/Programs/Python/Python313/python.exe' "$PSScriptRoot/rtl_test.py" $Version
if($LASTEXITCODE){throw 'RTL test generation failed'}
Push-Location "$PSScriptRoot/build/rtl_$Version"
try {
    & "$env:XILINX_VIVADO/bin/xvlog.bat" -prj sources.prj *> compile.log
    if($LASTEXITCODE){throw 'RTL compilation failed'}
    & "$env:XILINX_VIVADO/bin/xelab.bat" work.tb -s input_test -mt 4 *> elaborate.log
    if($LASTEXITCODE){throw 'RTL elaboration failed'}
    & "$env:XILINX_VIVADO/bin/xsim.bat" input_test -tclbatch run.tcl *> simulation.log
    if($LASTEXITCODE){throw 'RTL simulation failed'}
    if(-not(Select-String -LiteralPath simulation.log -SimpleMatch 'INPUT RTL PASS' -Quiet)){throw 'RTL checks failed'}
    Select-String -LiteralPath simulation.log -Pattern '^INPUT ' | ForEach-Object {$_.Line}
} finally {Pop-Location}
