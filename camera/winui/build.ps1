$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$env:PROCESSOR_ARCHITECTURE = 'AMD64'
$env:DOTNET_CLI_HOME = "$taskRoot/build/dotnet_home"
$env:NUGET_PACKAGES = "$taskRoot/build/nuget"
$env:NUGET_HTTP_CACHE_PATH = "$taskRoot/build/nuget_cache"
$env:TEMP = "$taskRoot/build/tmp"
$env:TMP = $env:TEMP
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
& "$taskRoot/build/dotnet/dotnet.exe" publish "$taskRoot/CNNStudio.csproj" -c Release -p:Platform=x64 -o "$taskRoot/build/delivery/CNNStudio"
if ($LASTEXITCODE) { throw 'WinUI build failed' }
$compiled = "$taskRoot/build/bin/x64/Release/net8.0-windows10.0.19041.0/win-x64"
Copy-Item "$compiled/*.xbf" "$taskRoot/build/delivery/CNNStudio"
Copy-Item "$compiled/CNNStudio.pri" "$taskRoot/build/delivery/CNNStudio"
foreach ($name in @('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll','msvcp140_atomic_wait.dll','msvcp140_codecvt_ids.dll','concrt140.dll')) {
    Copy-Item "$env:SystemRoot/System32/$name" "$taskRoot/build/delivery/CNNStudio"
}
