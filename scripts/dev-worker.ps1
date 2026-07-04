$ErrorActionPreference = "Stop"

$serverDir = Join-Path $PSScriptRoot "..\server"
$venvActivate = Join-Path $PSScriptRoot "..\server\.venv\Scripts\Activate.ps1"
if (Test-Path -LiteralPath $venvActivate) {
    . $venvActivate
}

Set-Location -LiteralPath $serverDir

$envPath = Join-Path $PSScriptRoot "..\.env"
Get-Content -LiteralPath $envPath | ForEach-Object {
    if ($_ -match "^\s*([^#=\s]+)=(.+)$") {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        Set-Item -Path "Env:$name" -Value $value
    }
}

uv run arq app.worker.WorkerSettings
