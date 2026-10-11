param(
    [string]$Script = 'run.tcl',
    [string]$WeightDirectory = 'C:\00_workplace\【雪天鱼】基于 HLS 的通用型CNN卷积加速器设计与实现V1.3\For SD card\folded_weight\BasicConv1'
)
$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'prepare.py') $WeightDirectory
if ($LASTEXITCODE) { throw 'PC weight file validation failed' }
$env:XILINX_VITIS = 'C:\AMDDesignTools\2026.1\Vitis'
$env:XILINX = $env:XILINX_VITIS
$env:TCL_LIBRARY = 'C:/AMDDesignTools/2026.1/Vitis/tps/tcl/tcl8.6'
$env:TCLLIBPATH = 'C:/AMDDesignTools/2026.1/Vitis/scripts/xsdb C:/AMDDesignTools/2026.1/Vitis/tps/tcl/tcllib2.0'
$env:PATH = "$env:XILINX_VITIS\lib\win64.o;$env:XILINX_VITIS\bin\unwrapped\win64.o;$env:PATH"
$taskProcess = Start-Process -FilePath "$env:XILINX_VITIS\bin\unwrapped\win64.o\xsdb.exe" -ArgumentList '-n',(Join-Path $PSScriptRoot $Script) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot 'xsdb.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'xsdb.stderr.log')
if (-not $taskProcess.WaitForExit(55000)) { throw "XSDB still running: PID $($taskProcess.Id)" }
Get-Content (Join-Path $PSScriptRoot 'xsdb.stdout.log'),(Join-Path $PSScriptRoot 'xsdb.stderr.log')
if ($taskProcess.ExitCode) { throw "XSDB exit $($taskProcess.ExitCode)" }
