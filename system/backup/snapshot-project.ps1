param([string]$Destination = (Join-Path $PSScriptRoot '..\..\.control-center\snapshots'))
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path; New-Item -ItemType Directory -Force $Destination|Out-Null
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'; $zip=Join-Path $Destination "game1_project_$stamp.zip"
Compress-Archive -Path (Join-Path $Root '*') -DestinationPath $zip -CompressionLevel Optimal
Write-Host $zip
