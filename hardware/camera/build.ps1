$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'vivado_env.ps1')
& "$env:XILINX_VIVADO/bin/vivado.bat" -mode batch -nolog -nojournal -source (Join-Path $PSScriptRoot 'build.tcl')
if ($LASTEXITCODE) { throw 'Camera hardware build failed' }
