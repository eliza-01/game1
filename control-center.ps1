[CmdletBinding()]param([switch]$NoBrowser)
$ErrorActionPreference='Stop'; $Root=$PSScriptRoot; $Runtime=Join-Path $Root '.control-center'; New-Item -ItemType Directory -Force $Runtime|Out-Null
$PidFile=Join-Path $Runtime 'agent.pid'; $Log=Join-Path $Runtime 'agent.log'; $Err=Join-Path $Runtime 'agent-error.log'
if(Test-Path $PidFile){$old=[int](Get-Content $PidFile -ErrorAction SilentlyContinue); if($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)){Stop-Process -Id $old -Force}}
$p=Start-Process python -ArgumentList @((Join-Path $Root 'system\control-center\host_agent.py')) -WorkingDirectory $Root -RedirectStandardOutput $Log -RedirectStandardError $Err -PassThru -WindowStyle Hidden
$p.Id | Set-Content $PidFile
Push-Location (Join-Path $Root 'system\control-center'); try { docker compose up -d --build } finally { Pop-Location }
Write-Host 'game1 Control Center: http://127.0.0.1:43820'; Write-Host 'Host agent: 127.0.0.1:43821'
if(-not $NoBrowser){Start-Process 'http://127.0.0.1:43820'}
