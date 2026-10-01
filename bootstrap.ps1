[CmdletBinding()]param([switch]$SkipDocker,[switch]$ForcePlaceBuild)
$ErrorActionPreference='Stop'
$Root=$PSScriptRoot
function Need($cmd){ if(-not (Get-Command $cmd -ErrorAction SilentlyContinue)){ throw "Required command is not available: $cmd" } }

# Safety boundary: game1 must be a sibling project, never a child/overlay of RobloxLineage.
if($Root -match '(?i)RobloxLineage'){
    throw "Refusing to bootstrap game1 from a path containing 'RobloxLineage'. Extract game1 into its own sibling directory first."
}
if(Test-Path (Join-Path $Root 'place\current.rbxl')){
    throw "Refusing to bootstrap: place\\current.rbxl exists. game1 uses place\\game1.rbxl only; current.rbxl may be the RobloxLineage place."
}

Need python
Need rokit
if(-not $SkipDocker){ Need docker }
Push-Location $Root
try {
    Write-Host '=== game1 bootstrap ==='
    rokit install
    Need rojo
    rojo plugin install
    & (Join-Path $Root 'system\studio-plugin\install.ps1')
    if($ForcePlaceBuild){
        & (Join-Path $Root 'place\build-place.ps1') -Force
    } elseif(-not (Test-Path (Join-Path $Root 'place\game1.rbxl'))){
        & (Join-Path $Root 'place\build-place.ps1')
    } else {
        Write-Host 'place\game1.rbxl already exists; leaving it untouched.'
    }
    & python (Join-Path $Root 'system\verify\verify.py')
    if(-not $SkipDocker){ & (Join-Path $Root 'control-center.ps1') -NoBrowser }
    Write-Host ''
    Write-Host 'BOOTSTRAP OK'
    Write-Host 'Open place\game1.rbxl in Studio. In the Rojo plugin connect to 127.0.0.1:34882, then run .\sync.ps1 in a separate PowerShell window.'
} finally { Pop-Location }
