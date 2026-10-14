$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../../hardware/camera/vivado_env.ps1')
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskSystem = Join-Path $PSScriptRoot 'build/system_profile'
New-Item -ItemType Directory -Force $taskSystem | Out-Null
foreach ($taskName in @('base_system.tcl', 'camera.xdc', 'ov5640_capture.v')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot "hardware/camera/$taskName") -Destination $taskSystem
}
$taskTcl = Get-Content -Raw (Join-Path $taskRoot 'hardware/camera/build.tcl')
$taskRepo = (Join-Path $PSScriptRoot 'build/profile/hls/impl/ip').Replace('\', '/')
$taskTcl = $taskTcl.Replace('[file join $source_dir ../hls/build/conv/hls/impl/ip]', "{$taskRepo}")
Set-Content -LiteralPath (Join-Path $taskSystem 'build.tcl') -Value $taskTcl
& "$env:XILINX_VIVADO/bin/vivado.bat" -mode batch -nolog -nojournal -source (Join-Path $taskSystem 'build.tcl')
if ($LASTEXITCODE) { throw 'Conv output profile hardware qualification failed' }
