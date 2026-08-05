# setup_threed.ps1
# One-time setup for the 3D agent.
# Run ONCE from the backend/ directory: .\setup_threed.ps1

$ErrorActionPreference = "Stop"
$py = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"

# Fix Windows Unicode encoding issue with Modal CLI output
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "Step 1: Deploying threed-agent (builds CUDA extensions)..." -ForegroundColor Cyan
& $py -m modal deploy agents/threed-agent/modal_app.py
if ($LASTEXITCODE -ne 0) { Write-Host "Deploy failed!" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Step 2: Downloading Hunyuan3D-2 weights into threed-weights-vol..." -ForegroundColor Cyan
Write-Host "(Large download: 10-20 min. Stored in Modal Volume, no repeat needed)" -ForegroundColor Yellow
& $py -m modal run agents/threed-agent/modal_app.py::setup_model_weights
if ($LASTEXITCODE -ne 0) { Write-Host "Weight download failed! Check HF token." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "threed-agent setup complete!" -ForegroundColor Green
