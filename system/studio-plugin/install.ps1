[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Generated=Join-Path $Root 'generated\Game1Bridge.rbxmx'
if(-not $env:LOCALAPPDATA){throw 'LOCALAPPDATA is not available'}
$Plugins=Join-Path $env:LOCALAPPDATA 'Roblox\Plugins'
$Installed=Join-Path $Plugins 'Game1Bridge.rbxmx'
$Temp=Join-Path $env:TEMP ("Game1Bridge-build-{0}.rbxmx" -f $PID)

New-Item -ItemType Directory -Force (Split-Path $Generated)|Out-Null
New-Item -ItemType Directory -Force $Plugins|Out-Null
Remove-Item $Temp -Force -ErrorAction SilentlyContinue

Push-Location $PSScriptRoot
try {
    rojo build plugin.project.json -o $Temp
} finally {
    Pop-Location
}

if(-not (Test-Path $Temp)){throw 'Rojo did not create the plugin build'}
$BuiltText=Get-Content $Temp -Raw
foreach($Marker in @('Game1ControlCenter','model bridge v20','Game1AttackTimeline_v2','TimelinePreviewWorld','location-authoring','Game1LocationMarker','Game1DecoManager_v1','DecoPreviewWorld','Save Assets Data','Game1DecoAssets')){
    if(-not $BuiltText.Contains($Marker)){
        throw "Studio bridge build is stale or incomplete; missing marker: $Marker"
    }
}
foreach($RemovedMarker in @('Game1CheckAnimations','Check Roblox Assets Animations','KeyframeSequenceProvider','/api/studio/animation-check')){
    if($BuiltText.Contains($RemovedMarker)){
        throw "Studio bridge still contains removed animation-check code: $RemovedMarker"
    }
}

Copy-Item $Temp $Generated -Force
Copy-Item $Temp $Installed -Force
$GeneratedHash=(Get-FileHash $Generated -Algorithm SHA256).Hash
$InstalledHash=(Get-FileHash $Installed -Algorithm SHA256).Hash
if($GeneratedHash -ne $InstalledHash){throw 'Installed Studio bridge hash does not match generated bridge hash'}
Remove-Item $Temp -Force -ErrorAction SilentlyContinue

Write-Host ("Game1Bridge installed with DecoManager + Locations authoring + in-plugin Attack Timeline viewport preview: {0}" -f $Installed)
Write-Host ("SHA256: {0}" -f $InstalledHash)
Write-Host 'DecoManager places published Location Assets; Locations draw from Asset Manager / Locations; Attack Timeline opens from Asset Manager / Timelines.'
Write-Host 'Fully close every Roblox Studio window, then reopen Studio once.'
