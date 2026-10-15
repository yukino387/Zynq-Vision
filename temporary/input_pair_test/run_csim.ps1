$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../../hardware/camera/vivado_env.ps1')
$env:XILINX_VITIS='C:/AMDDesignTools/2026.1/Vitis'
$env:PATH="$env:XILINX_VITIS/bin;$env:XILINX_VITIS/lib/win64.o;$env:PATH"
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBuild=Join-Path $PSScriptRoot 'build'
$taskTest=Get-Content -Raw "$taskRoot/temporary/int8_rebuild_test/test.cpp"
$taskTest=$taskTest.Replace('"../../hardware/hls/src/','"candidate_src/').Replace('"build/model.h"','"../../int8_rebuild_test/build/model.h"')
Set-Content -LiteralPath "$taskBuild/network_test.cpp" -Value $taskTest -Encoding ascii
$taskConfig=@('part=xc7z020clg400-2','[hls]','flow_target=vivado','clock=7','syn.top=conv','syn.interface.m_axi_addr64=0','csim.code_analyzer=0')
foreach($taskName in @('top','std_conv','maxpool','upsample')) {
    $taskSource=(Join-Path $taskBuild "candidate_src/$taskName.cpp").Replace('\','/')
    $taskConfig+="syn.file=$taskSource"
}
$taskConfig+='tb.file='+((Join-Path $taskBuild 'network_test.cpp').Replace('\','/'))
Set-Content -LiteralPath "$taskBuild/csim.cfg" -Value $taskConfig -Encoding ascii
& "$env:XILINX_VITIS/bin/vitis-run.bat" --mode hls --csim --config "$taskBuild/csim.cfg" --work_dir "$taskBuild/csim" *> "$taskBuild/csim.log"
if($LASTEXITCODE){throw 'Network C simulation failed; see csim.log'}
Select-String -LiteralPath "$taskBuild/csim.log" -Pattern 'PASS PS scheduled|CSim done'
