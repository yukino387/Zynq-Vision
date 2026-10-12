$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../camera/vivado_env.ps1')
$env:XILINX_VITIS = 'C:/AMDDesignTools/2026.1/Vitis'
$env:PATH = "$env:XILINX_VITIS/bin;$env:XILINX_VITIS/lib/win64.o;$env:PATH"
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'build') | Out-Null
Push-Location (Join-Path $PSScriptRoot 'build')
try {
    & "$env:XILINX_VITIS/bin/vitis-run.bat" --mode hls --tcl (Join-Path $PSScriptRoot 'build.tcl')
    if ($LASTEXITCODE) { throw 'Conv HLS build failed' }
} finally { Pop-Location }
