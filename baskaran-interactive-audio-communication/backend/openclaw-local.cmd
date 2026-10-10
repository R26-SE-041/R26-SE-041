@echo off
setlocal
set "PATH=%~dp0.actions-runtime\node-v24.21.0-win-x64;%PATH%"
set "OPENCLAW_STATE_DIR=%~dp0.actions-runtime\openclaw-state"
set "OPENCLAW_CONFIG_PATH=%OPENCLAW_STATE_DIR%\openclaw.json"
call "%~dp0.actions-runtime\openclaw\openclaw.cmd" %*
exit /b %ERRORLEVEL%
