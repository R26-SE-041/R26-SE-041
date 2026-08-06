# serve_all.ps1
# Runs 4 lightweight agents via `modal serve` (dev tunnel).
# threed-agent uses `modal deploy` since it needs CUDA extension builds.
#
# Usage: Right-click -> "Run with PowerShell"  OR  .\serve_all.ps1

# Fix Windows Unicode encoding issue with Modal CLI output
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- 4 core agents: serve via dev tunnel ---
$serveAgents = @(
    "agents/prompt-agent/modal_app.py",
    "agents/image-agent/modal_app.py",
    "agents/interactive-agent/modal_app.py",
    "agents/eval-agent/modal_app.py"
)

foreach ($agent in $serveAgents) {
    $title = ($agent -split "/")[1]   # e.g. "prompt-agent"
    Start-Process powershell -ArgumentList `
        "-NoExit", "-Command", `
        "`$env:PYTHONUTF8='1'; `$env:PYTHONIOENCODING='utf-8'; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; chcp 65001; cd '$PSScriptRoot'; ..\.venv\Scripts\python.exe -m modal serve $agent" `
        -WindowStyle Normal
    Write-Host "Started (serve): $title"
    Start-Sleep -Seconds 1
}

# --- threed-agent: deploy (builds CUDA extensions in Modal cloud) ---
Write-Host ""
Write-Host "Deploying threed-agent to Modal (builds CUDA extensions - takes ~2-3 min first time)..."
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command", `
    "`$env:PYTHONUTF8='1'; `$env:PYTHONIOENCODING='utf-8'; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; chcp 65001; cd '$PSScriptRoot'; ..\.venv\Scripts\python.exe -m modal deploy agents/threed-agent/modal_app.py" `
    -WindowStyle Normal
Write-Host "Started (deploy): threed-agent"

Write-Host ""
Write-Host "All agents launching."
Write-Host "4 agents in serve (dev) mode - close window to stop."
Write-Host "threed-agent deploying to Modal cloud - stays live even after window close."
