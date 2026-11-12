# Explicit opt-in installation of Fire Tuner M305. Independent from Game1Bridge.
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'fire-tuner\fire_bone.lua'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing Fire Tuner script: $source" }
if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is not available' }
$destination = Join-Path $env:LOCALAPPDATA 'Roblox\Plugins\fire_bone.lua'
$backupRoot = Join-Path $env:LOCALAPPDATA 'Game1\FireTunerBackups'
New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
if (Test-Path -LiteralPath $destination -PathType Leaf) {
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    $backup = Join-Path $backupRoot ('fire_bone_before_m305_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.lua')
    Copy-Item -LiteralPath $destination -Destination $backup -ErrorAction Stop
    Write-Host "Existing Fire Tuner backed up: $backup"
}
Copy-Item -LiteralPath $source -Destination $destination -Force -ErrorAction Stop
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash) {
    throw 'Fire Tuner installation hash mismatch'
}
Write-Host "Fire Tuner M305 installed: $destination"
Write-Host 'Restart Roblox Studio. This script never installs through Game1Bridge.'
