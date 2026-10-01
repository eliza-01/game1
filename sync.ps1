[CmdletBinding()]param([switch]$InstallPlugin)
$ErrorActionPreference='Stop'; $Root=$PSScriptRoot
& python (Join-Path $Root 'system\verify\verify.py'); if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
if($InstallPlugin){ Push-Location $Root; try { rojo plugin install } finally { Pop-Location } }
Write-Host 'Starting game1 Rojo on 127.0.0.1:34882'
Push-Location $Root; try { rojo serve default.project.json --port 34882 } finally { Pop-Location }
