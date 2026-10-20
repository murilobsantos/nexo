param([switch]$KeepBackend)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot '.runtime/nexo.pid'
if (Test-Path -LiteralPath $pidFile) {
    $coreId = [int](Get-Content -LiteralPath $pidFile)
    $core = Get-Process -Id $coreId -ErrorAction SilentlyContinue
    if ($core) {
        $expected = [IO.Path]::GetFullPath((Join-Path $projectRoot '.venv/Scripts/python.exe'))
        if ($core.Path -ne $expected) { throw 'PID reutilizado por outro executável; parada recusada.' }
        try {
            Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/api/mode' -ContentType 'application/json' -Body '{"mode":"paused"}' -TimeoutSec 10 | Out-Null
        } catch { Write-Warning 'API indisponível: recuperação de tarefa será aplicada no próximo início.' }
        & taskkill.exe /PID $coreId /T /F
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao encerrar núcleo.' }
    }
    Remove-Item -LiteralPath $pidFile
}
if (-not $KeepBackend) { & (Join-Path $PSScriptRoot 'stop-local.ps1') }
