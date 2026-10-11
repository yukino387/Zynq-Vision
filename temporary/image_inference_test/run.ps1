param([Parameter(Mandatory=$true)][string]$WeightDirectory, [string]$ImagePath)
$ErrorActionPreference = 'Stop'
$taskPython = (Get-Command python -ErrorAction Stop).Source
$taskPrepareArgs = @((Join-Path $PSScriptRoot 'prepare.py'), $WeightDirectory)
if ($ImagePath) { $taskPrepareArgs += $ImagePath }
& $taskPython @taskPrepareArgs
if ($LASTEXITCODE) { throw 'PC weight file validation failed' }
& (Join-Path $PSScriptRoot 'build.ps1')
$env:XILINX_VITIS = 'C:\AMDDesignTools\2026.1\Vitis'
$env:XILINX = $env:XILINX_VITIS
$env:TCL_LIBRARY = 'C:/AMDDesignTools/2026.1/Vitis/tps/tcl/tcl8.6'
$env:TCLLIBPATH = 'C:/AMDDesignTools/2026.1/Vitis/scripts/xsdb C:/AMDDesignTools/2026.1/Vitis/tps/tcl/tcllib2.0'
$env:PATH = "$env:XILINX_VITIS\lib\win64.o;$env:XILINX_VITIS\bin\unwrapped\win64.o;$env:PATH"
$taskProcess = Start-Process -FilePath "$env:XILINX_VITIS\bin\unwrapped\win64.o\xsdb.exe" -ArgumentList '-n',(Join-Path $PSScriptRoot 'run.tcl') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot 'xsdb.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'xsdb.stderr.log')
while (-not $taskProcess.WaitForExit(10000)) { Write-Output "Image inference test running (PID $($taskProcess.Id))" }
Get-Content (Join-Path $PSScriptRoot 'result.log')
if ($taskProcess.ExitCode) { throw "XSDB exit $($taskProcess.ExitCode)" }
& $taskPython (Join-Path $PSScriptRoot "report.py")
if ($LASTEXITCODE) { throw "Output validation failed" }
