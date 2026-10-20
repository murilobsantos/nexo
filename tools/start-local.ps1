$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
$env:OLLAMA_MODELS = Join-Path $runtimeRoot 'models'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_KEEP_ALIVE = '0'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_CONTEXT_LENGTH = '2048'
$executable = Join-Path $runtimeRoot 'ollama/ollama.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Ollama portátil ausente.' }
if (Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -InformationLevel Quiet -WarningAction SilentlyContinue) {
    throw 'Porta 11434 ocupada. Não assumindo controle de outro servidor.'
}
$server = Start-Process -FilePath $executable -ArgumentList 'serve' -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runtimeRoot 'logs/server.out.log') `
    -RedirectStandardError (Join-Path $runtimeRoot 'logs/server.err.log')
$server.Id | Set-Content -LiteralPath (Join-Path $runtimeRoot 'server.pid')
Write-Output "Servidor local iniciado: PID $($server.Id). Use tools/stop-local.ps1 para encerrar."
