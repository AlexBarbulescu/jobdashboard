Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $repoRoot "data\run"

foreach ($name in @("web", "worker")) {
    $pidPath = Join-Path $runDir "$name.pid"
    if (-not (Test-Path $pidPath)) {
        Write-Host "$name is not running"
        continue
    }

    $pidValue = Get-Content $pidPath -ErrorAction SilentlyContinue
    if ($pidValue) {
        $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $pidValue -Force
            Write-Host "Stopped $name (PID $pidValue)"
        } else {
            Write-Host "$name PID file existed but the process was already gone"
        }
    }

    Remove-Item $pidPath -ErrorAction SilentlyContinue
}