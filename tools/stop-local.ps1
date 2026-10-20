$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot '.runtime/server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Output 'Nenhum PID registrado.'; exit }
$serverId = [int](Get-Content -LiteralPath $pidFile)
$server = Get-Process -Id $serverId -ErrorAction SilentlyContinue
if ($server) {
    $expected = [IO.Path]::GetFullPath((Join-Path $projectRoot '.runtime/ollama/ollama.exe'))
    if ($server.Path -ne $expected) { throw 'PID reutilizado por outro processo; encerramento recusado.' }
    # taskkill encerra também runners descendentes do servidor registrado.
    & taskkill.exe /PID $serverId /T /F
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao encerrar servidor.' }
}
Remove-Item -LiteralPath $pidFile
