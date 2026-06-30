$ErrorActionPreference = "Stop"

$serverDir = Join-Path $PSScriptRoot "..\server"
$venvActivate = Join-Path $PSScriptRoot "..\server\.venv\Scripts\Activate.ps1"
if (Test-Path -LiteralPath $venvActivate) {
    . $venvActivate
}

Set-Location -LiteralPath $serverDir

$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_USER = "evidentrag"
$env:POSTGRES_PASSWORD = "evidentrag"
$env:POSTGRES_DB = "evidentrag"

$env:QDRANT_URL = "http://localhost:6333"
$env:EVIDENCE_COLLECTION_NAME = "evidentrag_evidence"

$env:REDIS_URL = "redis://localhost:6379"

$env:LLM_API_BASE = "http://optiplex-3020:8081/v1"
$env:LLM_API_KEY = "1d58046a3b2c79ef"
$env:GEMINI_EMBEDDING_MODEL = "google/gemini-embedding-2"
$env:GEMINI_EMBEDDING_DIMENSIONS = "768"
$env:LOG_FORMAT = "pretty"

$env:SEED_DEMO_DATA = "false"

uvicorn app.main:app --reload
