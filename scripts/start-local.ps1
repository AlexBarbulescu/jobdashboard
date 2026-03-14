Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot "venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $pythonCommand = $venvPython
    $pythonPrefix = @()
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command python).Source
    $pythonPrefix = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command py).Source
    $pythonPrefix = @("-3")
} else {
    throw "Python 3 was not found. Install Python 3.11+ or create the venv first."
}

$runDir = Join-Path $repoRoot "data\run"
$logDir = Join-Path $repoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Start-ManagedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $stdoutPath = Join-Path $logDir "$Name.out.log"
    $stderrPath = Join-Path $logDir "$Name.err.log"
    $pidPath = Join-Path $runDir "$Name.pid"

    if (Test-Path $pidPath) {
        $existingPid = Get-Content $pidPath -ErrorAction SilentlyContinue
        if ($existingPid) {
            $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
            if ($existingProcess) {
                Write-Host "$Name is already running with PID $existingPid"
                return $existingProcess
            }
        }
        Remove-Item $pidPath -ErrorAction SilentlyContinue
    }

    $fullArguments = $pythonPrefix + $Arguments
    $process = Start-Process -FilePath $pythonCommand -ArgumentList $fullArguments -WorkingDirectory $repoRoot -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru

    Set-Content -Path $pidPath -Value $process.Id
    Write-Host "Started $Name with PID $($process.Id)"
    return $process
}

Start-ManagedProcess -Name "worker" -Arguments @("-m", "worker.main") | Out-Null
Start-ManagedProcess -Name "web" -Arguments @("-m", "streamlit", "run", "web/app.py", "--server.port=8501", "--server.address=0.0.0.0") | Out-Null

Write-Host "Dashboard: http://localhost:8501"
Write-Host "Logs: data/logs"
Write-Host "Stop both services with .\scripts\stop-local.ps1"