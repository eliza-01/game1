[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Generated=Join-Path $Root 'generated\Game1Bridge.rbxmx'
$Plugins=Join-Path $env:LOCALAPPDATA 'Roblox\Plugins'
if(-not $env:LOCALAPPDATA){throw 'LOCALAPPDATA is not available'}
New-Item -ItemType Directory -Force (Split-Path $Generated)|Out-Null
New-Item -ItemType Directory -Force $Plugins|Out-Null
Push-Location $PSScriptRoot
try { rojo build plugin.project.json -o $Generated } finally { Pop-Location }
Copy-Item $Generated (Join-Path $Plugins 'Game1Bridge.rbxmx') -Force
Write-Host 'Game1Bridge plugin installed. Restart Roblox Studio once.'
