$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../../hardware/camera/vivado_env.ps1')
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskSystem = Join-Path $PSScriptRoot 'build/system125'
New-Item -ItemType Directory -Force $taskSystem | Out-Null
foreach ($taskName in @('base_system.tcl','camera.xdc','ov5640_capture.v')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot "hardware/camera/$taskName") -Destination $taskSystem
}
$taskTcl = Get-Content -Raw (Join-Path $taskRoot 'hardware/camera/build.tcl')
$taskRepo = (Join-Path $PSScriptRoot 'build/aligned_synthesis/hls/impl/ip').Replace('\','/')
$taskTcl = $taskTcl.Replace('[file join $source_dir ../hls/build/conv/hls/impl/ip]', "{$taskRepo}")
$taskTcl = "set_param general.maxThreads 8`n" + $taskTcl
Set-Content -LiteralPath (Join-Path $taskSystem 'build.tcl') -Value $taskTcl
& "$env:XILINX_VIVADO/bin/vivado.bat" -mode batch -nolog -nojournal -source (Join-Path $taskSystem 'build.tcl')
if ($LASTEXITCODE) { throw 'INT8 camera hardware build failed' }
$taskQualified = Join-Path $PSScriptRoot 'build/qualified125'
New-Item -ItemType Directory -Force $taskQualified | Out-Null
foreach ($taskName in @('system_wrapper.bit','camera_cnn.xsa','qualified.dcp','timing.rpt','bus_skew.rpt','utilization.rpt')) {
    Copy-Item -LiteralPath (Join-Path $taskSystem "build/$taskName") -Destination $taskQualified -Force
}
