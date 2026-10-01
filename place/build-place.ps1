[CmdletBinding()]param([switch]$Force)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Output=Join-Path $PSScriptRoot 'game1.rbxl'
$Legacy=Join-Path $PSScriptRoot 'current.rbxl'

if(Test-Path $Legacy){
    throw "Refusing to continue: place\\current.rbxl exists. game1 never uses current.rbxl; it may belong to RobloxLineage. Move/remove it from the game1 directory first."
}
if((Test-Path $Output) -and -not $Force){
    throw "Refusing to overwrite existing place\\game1.rbxl. Re-run with -Force only if you intentionally want to regenerate the clean Rojo place."
}

Push-Location $Root
try { rojo build default.project.json -o $Output } finally { Pop-Location }
Write-Host "Built clean game1 place: $Output"
