param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('visakanbaskaran','krishnavaranan1','krishnavaranan','varananrp')]
    [string]$Workspace,
    [string]$PythonExecutable
)
$ErrorActionPreference = 'Stop'
$backendDirectory = $PSScriptRoot
if (-not $PythonExecutable) {
    $portableCandidate = Join-Path (Split-Path (Split-Path $backendDirectory -Parent) -Parent) '..\.python-portable\python.exe'
    if (Test-Path -LiteralPath $portableCandidate) {
        $PythonExecutable = (Resolve-Path -LiteralPath $portableCandidate).Path
    } else {
        $PythonExecutable = (Get-Command python -ErrorAction Stop).Source
    }
}
# Check ownership before changing configuration or stopping the component.
$recordedProcess = $null
$pidFile = Join-Path $backendDirectory 'backend-runtime.pid'
if (Test-Path -LiteralPath $pidFile) {
    $backendProcessId = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
    $recordedProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $backendProcessId" -ErrorAction SilentlyContinue
    if ($recordedProcess) {
        if ($recordedProcess.CommandLine -notmatch 'uvicorn\s+app\.main:app') {
            throw 'Recorded PID belongs to another process. Restart backend manually.'
        }
    }
}
$portOwner = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portOwner -and (-not $recordedProcess -or @($portOwner | Where-Object { $_.OwningProcess -ne $backendProcessId }).Count -gt 0)) {
    throw 'Port 8000 belongs to another server. Configuration was not changed.'
}
& $PythonExecutable -X utf8 (Join-Path $backendDirectory 'scripts\modal_workspaces.py') switch $Workspace
if ($LASTEXITCODE -ne 0) { throw 'Workspace verification guard rejected the switch.' }
if ($recordedProcess) {
    Stop-Process -Id $backendProcessId -ErrorAction Stop
    Wait-Process -Id $backendProcessId -Timeout 15 -ErrorAction SilentlyContinue
}
$portOwner = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portOwner) { throw 'Port 8000 is occupied. Configuration selected; restart backend manually.' }
$process = Start-Process -FilePath $PythonExecutable -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $backendDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $backendDirectory 'backend-runtime.stdout.log') -RedirectStandardError (Join-Path $backendDirectory 'backend-runtime.stderr.log')
Set-Content -LiteralPath $pidFile -Value $process.Id
Write-Host "Backend started with $Workspace (PID $($process.Id))."
