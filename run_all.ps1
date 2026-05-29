<#
Run all services (docker compose) for local dev and tail logs.

Usage:
  .\run_all.ps1            # build, start in background, wait for readiness, tail logs
  .\run_all.ps1 -NoLogs   # start but don't tail logs
  .\run_all.ps1 -Stop     # stop and remove containers

# Requires: Docker Desktop or docker+docker-compose on PATH
#
# This script tries `docker compose` first, then `docker-compose`.
#
#> 

param(
    [switch]$Stop,
    [switch]$NoLogs
)

function Find-ComposeCmd {
    $cmd = $null
    try {
        docker compose version > $null 2>&1
        $cmd = 'docker compose'
    } catch {
        try {
            docker-compose version > $null 2>&1
            $cmd = 'docker-compose'
        } catch {
            $cmd = $null
        }
    }
    return $cmd
}

function Exec-Compose($args) {
    $compose = Find-ComposeCmd
    if (-not $compose) {
        Write-Error "docker compose not found. Install Docker Desktop or docker-compose and ensure it's on PATH."
        exit 1
    }
    Write-Host "Running: $compose $args"
    & $compose $args
    if ($LASTEXITCODE -ne 0) {
        Write-Error "docker compose returned exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

if ($Stop) {
    Exec-Compose 'down --volumes --remove-orphans'
    Write-Host "All services stopped and removed."
    exit 0
}

# Start services in background
Exec-Compose 'up --build -d'

Write-Host "Waiting for Redis container (sen_redis) to respond..."
$maxWait = 30
$i = 0
while ($i -lt $maxWait) {
    try {
        docker exec sen_redis redis-cli PING > $null 2>&1
        if ($LASTEXITCODE -eq 0) { break }
    } catch {
    }
    Start-Sleep -Seconds 1
    $i++
}
if ($i -ge $maxWait) {
    Write-Warning "Redis did not respond within $maxWait seconds. Check docker logs: docker logs sen_redis"
} else {
    Write-Host "Redis is responding (PONG)."
}

# Check orchestrator container presence
$orch = docker ps --filter "name=orchestrator" --format "{{.Names}}" 2>$null
if (-not $orch) {
    Write-Warning "Orchestrator container not found in 'docker ps'. It may be named with project prefix. Check 'docker ps' output."
} else {
    Write-Host "Orchestrator container(s):"
    $orch | ForEach-Object { Write-Host "  $_" }
}

if (-not $NoLogs) {
    Write-Host "Tailing docker-compose logs (press Ctrl+C to stop)..."
    Exec-Compose 'logs -f --tail=200'
} else {
    Write-Host "Started in background (no logs). Use '.\run_all.ps1 -Stop' to stop." 
}
