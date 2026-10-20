$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$runtimeRoot = Join-Path $projectRoot '.runtime'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Ambiente ausente. Siga a instalação no README.' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend/dist/index.html'))) { throw 'Interface ausente. Execute o build descrito no README.' }
function Test-LocalPort([int]$Port) {
    $client = [Net.Sockets.TcpClient]::new()
    try { return $client.ConnectAsync('127.0.0.1', $Port).Wait(500) -and $client.Connected }
    catch { return $false }
    finally { $client.Dispose() }
}
if (Test-LocalPort 8765) { throw 'Porta 8765 ocupada; nenhum servidor foi substituído.' }
if (-not (Test-LocalPort 11434)) { & (Join-Path $PSScriptRoot 'start-local.ps1') }
else {
    $serverPidFile = Join-Path $runtimeRoot 'server.pid'
    if (-not (Test-Path -LiteralPath $serverPidFile)) { throw 'Backend existente não pertence a este runtime.' }
    $backendProcess = Get-Process -Id ([int](Get-Content -LiteralPath $serverPidFile)) -ErrorAction SilentlyContinue
    $expectedBackend = [IO.Path]::GetFullPath((Join-Path $runtimeRoot 'ollama/ollama.exe'))
    if (-not $backendProcess -or $backendProcess.Path -ne $expectedBackend) { throw 'Não foi possível verificar o backend existente.' }
}
$core = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'nexo') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runtimeRoot 'logs/nexo.out.log') `
    -RedirectStandardError (Join-Path $runtimeRoot 'logs/nexo.err.log')
$core.Id | Set-Content -LiteralPath (Join-Path $runtimeRoot 'nexo.pid')
Write-Output "NEXO iniciado: PID $($core.Id). Interface: http://127.0.0.1:8765"
