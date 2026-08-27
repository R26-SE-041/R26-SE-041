# serve_all.ps1
# Runs all browser-facing agents plus the orchestrator via `modal serve`
# (dev tunnel), including evaluation and 3D generation.
#
# Usage: Right-click -> "Run with PowerShell"  OR  .\serve_all.ps1

# Fix Windows Unicode encoding issue with Modal CLI output
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$venvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$runner = $null
if (Test-Path -LiteralPath $venvPython) {
    try {
        & $venvPython --version *> $null
        if ($LASTEXITCODE -eq 0) { $runner = "& '$venvPython' -m modal" }
    }
    catch { $runner = $null }
}
if (-not $runner) {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        try {
            & $pyCommand.Source -3.11 -m modal --version *> $null
            if ($LASTEXITCODE -eq 0) { $runner = "& '$($pyCommand.Source)' -3.11 -m modal" }
        }
        catch { $runner = $null }
    }
}
if (-not $runner) {
    $modalCommand = Get-Command modal -ErrorAction SilentlyContinue
    if ($modalCommand) { $runner = "& '$($modalCommand.Source)'" }
}
if (-not $runner) {
    throw "Modal CLI was not found. Install it with: py -3.11 -m pip install modal"
}

# --- Core agents + backend orchestrator: serve via dev tunnel ---
$serveAgents = @(
    "agents/prompt-agent/modal_app.py",
    "agents/image-agent/modal_app.py",
    "agents/interactive-agent/modal_app.py",
    "agents/eval-agent/modal_app.py",
    "agents/threed-agent/modal_app.py",
    "orchestrator/modal_app.py"
)

foreach ($agent in $serveAgents) {
    $parts = $agent -split "/"
    $title = if ($parts[0] -eq "orchestrator") { "backend-orchestrator" } else { $parts[1] }
    Start-Process powershell -ArgumentList `
        "-NoExit", "-Command", `
        "`$env:PYTHONUTF8='1'; `$env:PYTHONIOENCODING='utf-8'; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; chcp 65001; cd '$PSScriptRoot'; $runner serve $agent" `
        -WindowStyle Normal
    Write-Host "Started (serve): $title"
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "All agents launching."
Write-Host "5 agents + backend orchestrator in serve (dev) mode - close windows to stop."
Write-Host "Quality evaluation is enabled through eval-agent."
Write-Host "3D generation is enabled through threed-agent."
