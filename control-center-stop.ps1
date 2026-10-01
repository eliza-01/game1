$Root=$PSScriptRoot; $PidFile=Join-Path $Root '.control-center\agent.pid'
Push-Location (Join-Path $Root 'system\control-center'); try { docker compose down } finally { Pop-Location }
if(Test-Path $PidFile){$id=[int](Get-Content $PidFile -ErrorAction SilentlyContinue); if($id){Stop-Process -Id $id -Force -ErrorAction SilentlyContinue}; Remove-Item $PidFile -Force -ErrorAction SilentlyContinue}
