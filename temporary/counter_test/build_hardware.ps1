$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $taskRoot 'hardware/camera/vivado_env.ps1')
$taskSystem=Join-Path $PSScriptRoot 'build/system'
New-Item -ItemType Directory -Force $taskSystem | Out-Null
foreach($name in @('base_system.tcl','camera.xdc','ov5640_capture.v')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot "hardware/camera/$name") -Destination $taskSystem
}
$taskTcl=Get-Content -Raw (Join-Path $taskRoot 'hardware/camera/build.tcl')
$taskRepo=(Join-Path $PSScriptRoot 'build/ip').Replace('\','/')
$taskTcl=$taskTcl.Replace('[file join $source_dir ../hls/build/conv/hls/impl/ip]',"{$taskRepo}")
$taskTcl="set_param general.maxThreads 8`n"+$taskTcl
Set-Content -LiteralPath (Join-Path $taskSystem 'build.tcl') -Value $taskTcl
& "$env:XILINX_VIVADO/bin/vivado.bat" -mode batch -nolog -nojournal -source (Join-Path $taskSystem 'build.tcl')
if($LASTEXITCODE) {throw 'Counter hardware build failed'}
