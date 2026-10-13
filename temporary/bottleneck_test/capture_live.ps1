$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $taskRoot 'hardware/camera/vivado_env.ps1')
$taskNm='C:/AMDDesignTools/2026.1/Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-nm.exe'
$taskCommands=@('connect -url tcp:127.0.0.1:3121','targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}','stop')
& $taskNm (Join-Path $PSScriptRoot 'build/live/test.elf') | ForEach-Object {
    if($_ -match '^([0-9a-fA-F]+)\s+\w\s+(live_layer_us|live_poll_window_us|live_cpu)$') {
        $taskWords=switch($Matches[2]) {'live_cpu' {9};default {33}}
        $taskOutput=(Join-Path $PSScriptRoot ("build/"+$Matches[2]+'.bin')).Replace('\','/')
        $taskCommands+="mrd -bin -file {$taskOutput} 0x$($Matches[1]) $taskWords"
    }
}
if($taskCommands.Count -ne 6) {throw 'Diagnostic symbols missing'}
$taskCommands+=@('con','disconnect','exit')
$taskScript=Join-Path $PSScriptRoot 'build/capture_live.tcl'
$taskCommands | Set-Content $taskScript
& C:/AMDDesignTools/2026.1/Vitis/bin/xsdb.bat $taskScript
if($LASTEXITCODE) {throw 'Reading live counters failed'}
