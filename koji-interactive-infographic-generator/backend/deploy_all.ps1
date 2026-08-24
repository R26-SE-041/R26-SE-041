# Production deployment for all services changed by the feedback-memory system.
# Run from any directory: powershell -ExecutionPolicy Bypass -File .\deploy_all.ps1

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$targets = @(
    "agents/prompt-agent/modal_app.py",
    "agents/image-agent/modal_app.py",
    "agents/interactive-agent/modal_app.py",
    "agents/eval-agent/modal_app.py",
    "orchestrator/modal_app.py",
    "agents/skill-generator/modal_app.py"
)

$venvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$modalCommand = Get-Command modal -ErrorAction SilentlyContinue
$useVenvPython = $false
if (Test-Path -LiteralPath $venvPython) {
    try {
        & $venvPython --version *> $null
        $useVenvPython = $LASTEXITCODE -eq 0
    }
    catch {
        $useVenvPython = $false
    }
}

if (-not $useVenvPython -and -not $modalCommand) {
    throw "Modal CLI was not found. Activate/install the project environment before deploying."
}

Push-Location $PSScriptRoot
try {
    foreach ($target in $targets) {
        Write-Host ""
        Write-Host "Deploying $target ..." -ForegroundColor Cyan
        if ($useVenvPython) {
            & $venvPython -m modal deploy $target
        }
        else {
            & $modalCommand.Source deploy $target
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Deployment failed for $target (exit code $LASTEXITCODE). Remaining services were not deployed."
        }
        Write-Host "Deployed $target" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "All feedback-memory services deployed successfully." -ForegroundColor Green
}
finally {
    Pop-Location
}
