$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../../hardware/camera/vivado_env.ps1')
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$env:XILINX_VITIS = 'C:/AMDDesignTools/2026.1/Vitis'
$taskHls = Join-Path $PSScriptRoot 'build/burst_synthesis'
& "$env:XILINX_VITIS/bin/v++.bat" --compile --mode hls --config (Join-Path $PSScriptRoot 'hls_config.cfg') --work_dir $taskHls
if ($LASTEXITCODE) { throw 'PL dispatch HLS build failed' }
$taskSystem = Join-Path $PSScriptRoot 'build/burst_system'
New-Item -ItemType Directory -Force $taskSystem | Out-Null
foreach ($taskName in @('base_system.tcl','camera.xdc','ov5640_capture.v')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot "hardware/camera/$taskName") -Destination $taskSystem
}
$taskTcl = Get-Content -Raw (Join-Path $taskRoot 'hardware/camera/build.tcl')
$taskRepo = (Join-Path $taskHls 'hls/impl/ip').Replace('\','/')
$taskTcl = $taskTcl.Replace('[file join $source_dir ../hls/build/conv/hls/impl/ip]', "{$taskRepo}")
Set-Content -LiteralPath (Join-Path $taskSystem 'build.tcl') -Value $taskTcl
& "$env:XILINX_VIVADO/bin/vivado.bat" -mode batch -nolog -nojournal -source (Join-Path $taskSystem 'build.tcl')
if ($LASTEXITCODE) { throw 'PL dispatch camera hardware build failed' }
