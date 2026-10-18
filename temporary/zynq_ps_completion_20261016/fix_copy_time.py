from pathlib import Path
p=Path('camera/build_boot.ps1');s=p.read_text();a='-Destination (Join-Path $fsblSource $name) -Force';s=s.replace(a,a+'\n    (Get-Item -LiteralPath (Join-Path $fsblSource $name)).LastWriteTime = Get-Date');p.write_bytes(s.encode())
