# Convenience entry point for launching the complete development backend.
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "backend\serve_all.ps1")
