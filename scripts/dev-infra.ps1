$ErrorActionPreference = "Stop"

$composeArgs = @("compose", "up", "-d", "postgres", "qdrant", "redis")

docker @composeArgs
