$ErrorActionPreference='Stop'
$root=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$source=Join-Path $root 'camera/winui'
$test=Join-Path $PSScriptRoot 'build/ui'
New-Item -ItemType Directory -Force $test | Out-Null
Copy-Item "$source/*.cs","$source/*.xaml","$source/*.csproj","$source/*.props","$source/*.manifest" $test
Copy-Item "$source/Assets" $test -Recurse -Force
Copy-Item "$PSScriptRoot/TestApp.cs.txt" "$test/App.xaml.cs"
$env:DOTNET_CLI_HOME="$source/build/dotnet_home"
$env:NUGET_PACKAGES="$source/build/nuget"
$env:NUGET_HTTP_CACHE_PATH="$source/build/nuget_cache"
$env:TEMP="$source/build/tmp";$env:TMP=$env:TEMP
& "$source/build/dotnet/dotnet.exe" publish "$test/CNNStudio.csproj" -c Release -p:Platform=x64 -o "$test/build/app"
if($LASTEXITCODE){throw 'UI test build failed'}
$compiled="$test/build/bin/x64/Release/net8.0-windows10.0.19041.0/win-x64"
Copy-Item "$compiled/*.xbf","$compiled/CNNStudio.pri" "$test/build/app"
$info=New-Object System.Diagnostics.ProcessStartInfo
$info.FileName="$test/build/app/CNNStudio.exe";$info.UseShellExecute=$false
$process=[System.Diagnostics.Process]::Start($info)
if(!$process.WaitForExit(45000)){throw 'UI test timeout'}
Get-Content "$test/build/app/test_result.txt"
if(Test-Path "$test/build/app/test_error.log"){throw (Get-Content "$test/build/app/test_error.log" -Raw)}
