$ErrorActionPreference = "Stop"

$clientDir = Join-Path $PSScriptRoot "..\client"

Set-Location -LiteralPath $clientDir

npm run dev
