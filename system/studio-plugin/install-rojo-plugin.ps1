$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try { rojo plugin install } finally { Pop-Location }
Write-Host 'Rojo Studio plugin installed/updated.'
