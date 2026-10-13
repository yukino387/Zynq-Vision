$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBuild = Join-Path $PSScriptRoot 'build/decoder_test'
New-Item -ItemType Directory -Force $taskBuild | Out-Null
$env:DOTNET_CLI_HOME = "$taskRoot/camera/winui/build/dotnet_home"
$env:NUGET_PACKAGES = "$taskRoot/camera/winui/build/nuget"
$env:TEMP = "$taskRoot/camera/winui/build/tmp"
$env:TMP = $env:TEMP
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
Copy-Item -LiteralPath "$PSScriptRoot/decoder_test.cs" -Destination "$taskBuild/Program.cs"
@'
<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup><ItemGroup><Compile Include="../../../../camera/winui/Postprocess.cs" Link="Postprocess.cs" /></ItemGroup></Project>
'@ | Set-Content "$taskBuild/Decoder.csproj" -Encoding utf8
& "$taskRoot/camera/winui/build/dotnet/dotnet.exe" run --project "$taskBuild/Decoder.csproj" -c Release
if ($LASTEXITCODE) { throw 'INT8 decoder test failed' }
