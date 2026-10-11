param([string]$Script = 'run.tcl')
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $taskRoot 'hardware/camera/vivado_env.ps1')
$env:XILINX_VITIS = 'C:/AMDDesignTools/2026.1/Vitis'
$env:PATH = "$env:XILINX_VITIS/bin;$env:XILINX_VITIS/lib/win64.o;$env:PATH"
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'build') | Out-Null
Push-Location (Join-Path $PSScriptRoot 'build')
try {
    & "$env:XILINX_VITIS/bin/vitis-run.bat" --mode hls --tcl (Join-Path $PSScriptRoot $Script)
    if ($LASTEXITCODE -ne 0) { throw "HLS failed: $LASTEXITCODE" }
} finally { Pop-Location }
