# serve_all.ps1
# Runs the prompt, image, and interactive agents plus the orchestrator via
# `modal serve` (dev tunnel). Evaluation/reflection are disabled in the
# frontend flow and the eval agent can be started manually when needed.
# threed-agent uses `modal deploy` since it needs CUDA extension builds.
#
# Usage: Right-click -> "Run with PowerShell"  OR  .\serve_all.ps1

# Fix Windows Unicode encoding issue with Modal CLI output
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Core agents + backend orchestrator: serve via dev tunnel ---
$serveAgents = @(
    "agents/prompt-agent/modal_app.py",
    "agents/image-agent/modal_app.py",
    "agents/interactive-agent/modal_app.py",
    "orchestrator/modal_app.py"
)

foreach ($agent in $serveAgents) {
    $parts = $agent -split "/"
    $title = if ($parts[0] -eq "orchestrator") { "backend-orchestrator" } else { $parts[1] }
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
Write-Host "3 agents + backend orchestrator in serve (dev) mode - close windows to stop."
Write-Host "Evaluation/reflection are disabled. Start eval-agent manually only when required."
Write-Host "threed-agent deploying to Modal cloud - stays live even after window close."
