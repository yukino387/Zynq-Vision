$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../../hardware/camera/vivado_env.ps1')
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBuild=Join-Path $PSScriptRoot 'build'
$taskSystem=Join-Path $taskBuild 'system_candidate'
$taskExit=Join-Path $taskBuild 'hardware_exit.txt'
if(Test-Path -LiteralPath $taskExit){Remove-Item -LiteralPath $taskExit}
New-Item -ItemType Directory -Force $taskSystem | Out-Null
foreach($taskName in @('base_system.tcl','camera.xdc','ov5640_capture.v')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot "hardware/camera/$taskName") -Destination $taskSystem
}
$taskTcl=Get-Content -Raw (Join-Path $taskRoot 'hardware/camera/build.tcl')
$taskRepo=(Join-Path $taskBuild 'candidate/hls/impl/ip').Replace('\','/')
$taskTcl=$taskTcl.Replace('[file join $source_dir ../hls/build/conv/hls/impl/ip]',"{$taskRepo}")
$taskTcl=$taskTcl.Replace('write_checkpoint -force [file join $build_dir synthesized.dcp]',"write_checkpoint -force [file join `$build_dir synthesized.dcp]`nreport_utilization -file [file join `$build_dir synth_utilization.rpt]")
Set-Content -LiteralPath (Join-Path $taskSystem 'build.tcl') -Value $taskTcl -Encoding ascii
try {
    & "$env:XILINX_VIVADO/bin/vivado.bat" -mode batch -nolog -nojournal -source (Join-Path $taskSystem 'build.tcl') *> (Join-Path $taskBuild 'hardware.log')
    if($LASTEXITCODE){throw 'Paired input hardware qualification failed'}
    'PASS'|Set-Content -LiteralPath $taskExit
} catch {
    $_|Out-String|Write-Output
    'FAIL'|Set-Content -LiteralPath $taskExit
    exit 1
}
