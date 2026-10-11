$ErrorActionPreference = 'Stop'
$taskPython = (Get-Command python).Source
$taskPath = $env:PATH
# Keep external tool DLLs out of the Windows application package.
$env:PATH = "$([IO.Path]::GetDirectoryName($taskPython));$env:SystemRoot/System32;$env:SystemRoot"
Push-Location $PSScriptRoot
try {
    & $taskPython -m PyInstaller --noconfirm --clean --windowed --onedir --name CNNStudio --distpath build/dist --workpath build/work --specpath build app.py
    if ($LASTEXITCODE) { throw 'Desktop application packaging failed' }
} finally {
    Pop-Location
    $env:PATH = $taskPath
}
