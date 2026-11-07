[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Generated=Join-Path $Root 'generated\Game1Bridge.rbxmx'
if(-not $env:LOCALAPPDATA){throw 'LOCALAPPDATA is not available'}
$Plugins=Join-Path $env:LOCALAPPDATA 'Roblox\Plugins'
$Installed=Join-Path $Plugins 'Game1Bridge.rbxmx'
$Temp=Join-Path $env:TEMP ("Game1Bridge-build-{0}.rbxmx" -f $PID)
$RojoExe=(Get-Command rojo -ErrorAction Stop).Source
$RokitManifest=Join-Path $Root 'rokit.toml'
if($env:USERPROFILE -and (Test-Path -LiteralPath $RokitManifest -PathType Leaf)){
    $Pinned=(Select-String -LiteralPath $RokitManifest -Pattern 'rojo-rbx/rojo@([0-9.]+)' | Select-Object -First 1)
    if($Pinned){
        $RokitRojo=Join-Path $env:USERPROFILE ('.rokit\tool-storage\rojo-rbx\rojo\{0}\rojo.exe' -f $Pinned.Matches[0].Groups[1].Value)
        # Invoke the real pinned binary when available. Rokit's shim itself
        # requires a discoverable home directory and can fail in managed CI or
        # sandboxed shells even though the installed tool is fully usable.
        if(Test-Path -LiteralPath $RokitRojo -PathType Leaf){$RojoExe=$RokitRojo}
    }
}

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

# Rojo does not parse Luau. Catch dangerous source before replacing the
# working installed Game1Bridge; the previous M134 syntax issue hid all tools.
& python (Join-Path $PSScriptRoot 'validate_luau.py')
if($LASTEXITCODE -ne 0){throw 'Studio Luau preflight failed; installed plugin was not replaced'}

Push-Location $PSScriptRoot
try {
    & $RojoExe build plugin.project.json -o $Temp
    if($LASTEXITCODE -ne 0){throw 'Rojo Studio plugin build failed; installed plugin was not replaced'}
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
    'Game1CharacterStand',
    'StudioCharacterTestStand',
    'StudioCharacterStandBuilder',
    'StudioCharacterStandPlacement',
    'StudioCharacterStandWidget',
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
    'StudioHousePlacementPreview',
    'StudioPlotsCatalog',
    'StudioPlotsVisibility',
    'StudioPlotsPartPolicy',
    'StudioPlotsSelectionFilter',
    'Game1Plots',
    'Game1PlotsPreview',
    'StudioDebugPreferenceBridge',
    'StudioModelLoadCommands',
    'StudioRealEstateModel',
    'StudioRealEstatePartSync',
    'StudioRealEstateHouseFrame',
    'StudioRealEstatePartPlacement',
    'StudioRealEstateRigValidation',
    'StudioRealEstateCollisionPolicy',
    'StudioRealEstatePlacedPhysicsGuard',
    'StudioRealEstatePlacedCollisionSync',
    'StudioRealEstatePlacedVisualSync',
    'StudioManagedRigSwap',
    'StudioLocationPlacementOwner',
    'StudioLocationPlacedGeometry',
    'StudioLocationPublishedGeometry',
    'StudioLocationPlacementHistory',
    'StudioRealEstatePlacedTargets',
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

# Publishing a validated Rojo bundle is separate from building it. Windows may
# temporarily lock an existing .rbxmx as a memory-mapped file. Never delete a
# locked plugin or treat a partial copy as a successful installation.
function Install-VerifiedBundle {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [Parameter(Mandatory=$true)][string]$ExpectedHash
    )
    $MaxAttempts=5
    for($Attempt=1; $Attempt -le $MaxAttempts; $Attempt++){
        try {
            # Do not overwrite an identical bundle: this also avoids needless
            # writes to a file opened by Studio, a watcher or antivirus.
            if(Test-Path -LiteralPath $Destination -PathType Leaf){
                $ExistingHash=(Get-FileHash -LiteralPath $Destination -Algorithm SHA256 -ErrorAction Stop).Hash
                if($ExistingHash -eq $ExpectedHash){
                    Write-Host ("Studio bridge already current: {0}" -f $Destination)
                    return
                }
            }
            Copy-Item -LiteralPath $Source -Destination $Destination -Force -ErrorAction Stop
            $ActualHash=(Get-FileHash -LiteralPath $Destination -Algorithm SHA256 -ErrorAction Stop).Hash
            if($ActualHash -ne $ExpectedHash){
                throw "Copied Studio bridge hash mismatch: $Destination"
            }
            return
        } catch {
            $Failure=$_
            if($Attempt -eq $MaxAttempts){
                throw ("Studio bridge install failed: {0}. File may be locked by Roblox Studio, a build/watch process or another application. Close those processes and run ONLY system/studio-plugin/install.ps1 again; do NOT reapply the Git patch. Last error: {1}" -f $Destination, $Failure)
            }
            Start-Sleep -Milliseconds (200 * $Attempt)
        }
    }
}

$BuiltHash=(Get-FileHash -LiteralPath $Temp -Algorithm SHA256 -ErrorAction Stop).Hash
Install-VerifiedBundle -Source $Temp -Destination $Generated -ExpectedHash $BuiltHash
Install-VerifiedBundle -Source $Temp -Destination $Installed -ExpectedHash $BuiltHash
$GeneratedHash=(Get-FileHash $Generated -Algorithm SHA256).Hash
$InstalledHash=(Get-FileHash $Installed -Algorithm SHA256).Hash
if($GeneratedHash -ne $InstalledHash -or $GeneratedHash -ne $BuiltHash){
    throw 'Installed Studio bridge hash does not match the verified Rojo build'
}
Remove-Item $Temp -Force -ErrorAction SilentlyContinue

Write-Host ("Game1Bridge installed with DecoManager + authoring-marker visibility + Locations + Attack Timeline: {0}" -f $Installed)
Write-Host ("SHA256: {0}" -f $InstalledHash)
Write-Host 'DecoManager places published Location Assets; Locations draw from Asset Manager / Locations; Attack Timeline opens from Asset Manager / Timelines.'
Write-Host ("Studio modules: {0}; toolbar: Markers, Plots, DecoManager, Character Stand" -f $Declared.Count)
Write-Host 'Fully close every Roblox Studio window, then reopen Studio once.'
