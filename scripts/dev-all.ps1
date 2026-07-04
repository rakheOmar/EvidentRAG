$ErrorActionPreference = "Continue"

Write-Host "Starting infrastructure (postgres, qdrant, redis)..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "dev-infra.ps1")

Write-Host "Starting backend..." -ForegroundColor Cyan
$backendJob = Start-Job -FilePath (Join-Path $PSScriptRoot "dev-backend.ps1")

Write-Host "Starting frontend..." -ForegroundColor Cyan
$frontendJob = Start-Job -FilePath (Join-Path $PSScriptRoot "dev-frontend.ps1")

Write-Host "All services starting. Use the following commands to view logs:" -ForegroundColor Green
Write-Host "  Receive-Job -JobId $($backendJob.Id) -Keep" -ForegroundColor Yellow
Write-Host "  Receive-Job -JobId $($frontendJob.Id) -Keep" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop watching. Use Stop-Job to kill services." -ForegroundColor Gray

while ($true) {
    Start-Sleep -Seconds 5
}
