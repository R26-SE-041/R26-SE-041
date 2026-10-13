param(
    [string]$Account,
    [ValidateSet('switch', 'check', 'list', 'status', 'rollback')]
    [string]$Action = 'switch',
    [string]$Python
)
$ErrorActionPreference = 'Stop'
if ($Action -in @('switch', 'check') -and -not $Account) {
    throw 'Provide a configured account name.'
}
if (-not $Python) {
    $venvPython = Join-Path $PSScriptRoot '../.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $venvPython) { $Python = $venvPython }
    else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
Push-Location $PSScriptRoot
try {
    $arguments = @('-m', 'studio.modal_accounts', $Action)
    if ($Action -in @('switch', 'check')) { $arguments += $Account }
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Modal account operation failed (exit $LASTEXITCODE)." }
}
finally { Pop-Location }
