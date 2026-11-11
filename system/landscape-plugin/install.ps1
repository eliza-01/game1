[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Project = Join-Path $PSScriptRoot 'plugin.project.json'
$Generated = Join-Path $Root 'generated\Game1LandscapePainter.rbxmx'
if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is not available' }
$Installed = Join-Path $env:LOCALAPPDATA 'Roblox\Plugins\Game1LandscapePainter.rbxmx'
$Temp = Join-Path $env:TEMP ("Game1LandscapePainter-build-{0}.rbxmx" -f $PID)
$RojoExe = (Get-Command rojo -ErrorAction Stop).Source
$RokitManifest = Join-Path $Root 'rokit.toml'
if ($env:USERPROFILE -and (Test-Path -LiteralPath $RokitManifest)) {
    $Pinned = (Select-String -LiteralPath $RokitManifest -Pattern 'rojo-rbx/rojo@([0-9.]+)' | Select-Object -First 1)
    if ($Pinned) {
        $Pin = $Pinned.Matches[0].Groups[1].Value
        $RokitRojo = Join-Path $env:USERPROFILE ('.rokit\tool-storage\rojo-rbx\rojo\{0}\rojo.exe' -f $Pin)
        if (Test-Path -LiteralPath $RokitRojo -PathType Leaf) { $RojoExe = $RokitRojo }
    }
}

$Spec = Get-Content -LiteralPath $Project -Raw | ConvertFrom-Json
$Declared = @($Spec.tree.modules.PSObject.Properties | Where-Object { $_.Name -ne '$className' })
$Names = @($Declared | ForEach-Object { $_.Name })
foreach ($Entry in $Declared) {
    $Source = Join-Path $PSScriptRoot $Entry.Value.'$path'
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Missing Landscape Painter module: $($Entry.Name)"
    }
}
foreach ($Source in (Get-ChildItem (Join-Path $PSScriptRoot 'modules') -Filter '*.luau' -File)) {
    if ($Source.BaseName -notin $Names) { throw "Unmapped Landscape Painter module: $($Source.Name)" }
}
& python (Join-Path $Root 'system\studio-plugin\validate_luau.py') --plugin-dir $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Landscape Painter Luau preflight failed' }

New-Item -ItemType Directory -Force (Split-Path $Generated) | Out-Null
New-Item -ItemType Directory -Force (Split-Path $Installed) | Out-Null
Remove-Item -LiteralPath $Temp -Force -ErrorAction SilentlyContinue
Push-Location $PSScriptRoot
try {
    & $RojoExe build plugin.project.json -o $Temp
    if ($LASTEXITCODE -ne 0) { throw 'Landscape Painter Rojo build failed' }
} finally {
    Pop-Location
}
if (-not (Test-Path -LiteralPath $Temp -PathType Leaf)) { throw 'Rojo did not produce .rbxmx' }
try { [xml]$Xml = Get-Content -LiteralPath $Temp -Raw } catch { throw "Invalid rbxmx: $_" }
$Packaged = @($Xml.SelectNodes('//Item[@class="ModuleScript"]/Properties/string[@name="Name"]') | ForEach-Object { $_.InnerText })
foreach ($Name in $Names) {
    if ($Name -notin $Packaged) { throw "Build missing Landscape module: $Name" }
}
$ScriptNames = @($Xml.SelectNodes('//Item[@class="Script"]/Properties/string[@name="Name"]') | ForEach-Object { $_.InnerText })
if ('Main' -notin $ScriptNames) { throw 'Build missing main plugin script' }
$Hash = (Get-FileHash -LiteralPath $Temp -Algorithm SHA256).Hash
foreach ($Destination in @($Generated, $Installed)) {
    if ((Test-Path $Destination) -and (Get-FileHash $Destination -Algorithm SHA256).Hash -eq $Hash) {
        Write-Host "Already current: $Destination"
        continue
    }
    Copy-Item -LiteralPath $Temp -Destination $Destination -Force -ErrorAction Stop
    if ((Get-FileHash $Destination -Algorithm SHA256).Hash -ne $Hash) {
        throw "Installed Landscape Painter hash mismatch: $Destination"
    }
    Write-Host "Installed: $Destination"
}
Remove-Item -LiteralPath $Temp -Force -ErrorAction SilentlyContinue
Write-Host 'Game1LandscapePainter installed independently of Game1Bridge.'
Write-Host 'Close and reopen Roblox Studio to load the new plugin, then open the game1 landscape toolbar.'
