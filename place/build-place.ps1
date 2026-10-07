[CmdletBinding()]param([switch]$Force)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Output=Join-Path $PSScriptRoot 'game1.rbxl'
$Legacy=Join-Path $PSScriptRoot 'current.rbxl'
$LiveProject=Join-Path $Root 'default.project.json'
$BuildProject=Join-Path $Root '.build-place.project.json'

if(Test-Path $Legacy){
    throw "Refusing to continue: place\current.rbxl exists. game1 never uses current.rbxl; it may belong to RobloxLineage. Move/remove it from the game1 directory first."
}
if((Test-Path $Output) -and -not $Force){
    throw "Refusing to overwrite existing place\game1.rbxl. Re-run with -Force only if you intentionally want to regenerate the clean Rojo place."
}

# Live Rojo deliberately does not own authored Workspace children. For a brand
# new place build only, inject the minimal seed floor/spawn into a temporary
# project file. Once the place exists, Studio owns their transforms and other
# authored scene edits; live Rojo only syncs runtime code/services.
$Project=Get-Content -Raw $LiveProject | ConvertFrom-Json
$Workspace=$Project.tree.Workspace
$Baseplate=[pscustomobject]@{
    '$className'='Part'
    '$properties'=[pscustomobject]@{
        Anchored=$true
        CanCollide=$true
        Locked=$true
        Position=@(0,-0.5,0)
        Size=@(256,1,256)
    }
}
$SpawnLocation=[pscustomobject]@{
    '$className'='SpawnLocation'
    '$properties'=[pscustomobject]@{
        Anchored=$true
        CanCollide=$true
        Neutral=$true
        Position=@(0,0.5,0)
        Size=@(6,1,6)
    }
}
$Workspace | Add-Member -NotePropertyName 'Baseplate' -NotePropertyValue $Baseplate -Force
$Workspace | Add-Member -NotePropertyName 'SpawnLocation' -NotePropertyValue $SpawnLocation -Force
$Project | ConvertTo-Json -Depth 100 | Set-Content -Encoding UTF8 $BuildProject

Push-Location $Root
try {
    rojo build $BuildProject -o $Output
} finally {
    Pop-Location
    Remove-Item $BuildProject -Force -ErrorAction SilentlyContinue
}
Write-Host "Built clean game1 place: $Output"
Write-Host "Live Rojo will preserve authored Workspace children and transforms."
