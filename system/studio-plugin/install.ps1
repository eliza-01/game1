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

# Verify every source module is mapped into the Rojo build. Marker checks alone
# can pass even when an unrelated editor tool was accidentally left out.
$Project=Get-Content (Join-Path $PSScriptRoot 'plugin.project.json') -Raw | ConvertFrom-Json
$Declared=@($Project.tree.modules.PSObject.Properties | Where-Object { $_.Name -ne '$className' })
$DeclaredNames=@($Declared | ForEach-Object { $_.Name })
foreach($Entry in $Declared){
    $Source=Join-Path $PSScriptRoot $Entry.Value.'$path'
    if(-not (Test-Path $Source -PathType Leaf)){
        throw "Studio plugin module is declared but missing: $($Entry.Name) ($Source)"
    }
}
foreach($SourceFile in (Get-ChildItem (Join-Path $PSScriptRoot 'modules') -Filter '*.luau' -File)){
    if($SourceFile.BaseName -notin $DeclaredNames){
        throw "Studio plugin module is present but not in Rojo manifest: $($SourceFile.Name)"
    }
}

Push-Location $PSScriptRoot
try {
    rojo build plugin.project.json -o $Temp
} finally {
    Pop-Location
}

if(-not (Test-Path $Temp)){throw 'Rojo did not create the plugin build'}
$BuiltText=Get-Content $Temp -Raw
# Audit real compiled ModuleScript instances, not just Lua identifier strings.
# A Lua require may mention a missing module even when Rojo omitted the Item.
try { [xml]$BuiltXml=$BuiltText } catch { throw "Rojo output is not valid rbxmx XML: $_" }
$PackagedNames=@($BuiltXml.SelectNodes('//Item[@class="ModuleScript"]/Properties/string[@name="Name"]') | ForEach-Object { $_.InnerText })
foreach($ModuleName in $DeclaredNames){
    if($ModuleName -notin $PackagedNames){
        throw "Studio plugin built without declared module: $ModuleName"
    }
}
foreach($ModuleName in $PackagedNames){
    if($ModuleName -notin $DeclaredNames){
        throw "Studio plugin contains unexpected module: $ModuleName"
    }
}
# Validate the command API used by Asset Manager, not the removed Control Center toolbar button.
# The installer must reject old builds that lack the Monster/NPC Spawn command handler.
foreach($Marker in @(
    'model bridge v24',
    'local function checkAgent()',
    'local function handleMonsterSpawn(',
    'data.command == "monster-spawn"',
    'Game1MonsterSpawnMarker',
    'Game1NpcSpawnMarker',
    'Game1AttackTimeline_v2',
    'TimelinePreviewWorld',
    'location-authoring',
    'Game1LocationMarker',
    'Game1DecoManager_v1',
    'DecoPreviewWorld',
    'Save Assets Data',
    'Game1DecoAssets',
    'Game1AuthoringMarkers',
    'StudioMarkerVisibility',
    'StudioPlotsCatalog',
    'StudioPlotsVisibility',
    'StudioPlotsPartPolicy',
    'StudioPlotsSelectionFilter',
    'Game1Plots',
    'Game1PlotsPreview',
    'StudioDebugPreferenceBridge',
    'StudioModelLoadCommands',
    'StudioRealEstateModel',
    'StudioRealEstateRigValidation',
    'StudioRealEstateSocketRecovery',
    'StudioRealEstateCollisionPolicy',
    'StudioRealEstatePlacedCollisionSync',
    'StudioDecoSyncCommands',
    'StudioTextureAppearance',
    'StudioActorSpawnCommands'
    'StudioTimelineEditorCommands'
    'StudioTimelineWidget'
    'StudioTimelinePreview'
    'StudioTimelinePoseSampler'
    'StudioTimelineTransport'
)){
    if(-not $BuiltText.Contains($Marker)){
        throw "Studio bridge build is stale or incomplete; missing marker: $Marker"
    }
}
foreach($RemovedMarker in @('Game1ControlCenter','Game1CheckAnimations','Check Roblox Assets Animations','KeyframeSequenceProvider','/api/studio/animation-check')){
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

Write-Host ("Game1Bridge installed with DecoManager + authoring-marker visibility + Locations + Attack Timeline: {0}" -f $Installed)
Write-Host ("SHA256: {0}" -f $InstalledHash)
Write-Host 'DecoManager places published Location Assets; Locations draw from Asset Manager / Locations; Attack Timeline opens from Asset Manager / Timelines.'
Write-Host ("Studio modules: {0}; toolbar: Markers, Plots, DecoManager" -f $Declared.Count)
Write-Host 'Fully close every Roblox Studio window, then reopen Studio once.'
