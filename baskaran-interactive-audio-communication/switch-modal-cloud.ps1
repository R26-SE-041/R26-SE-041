<#
.SYNOPSIS
Switch the hosted VoiceLearn backend's Modal workspace from your laptop.
.EXAMPLE
.\switch-modal-cloud.ps1 krishnavaranan1
.EXAMPLE
.\switch-modal-cloud.ps1 -Status
.EXAMPLE
.\switch-modal-cloud.ps1 varananrp -Preview
#>
[CmdletBinding(DefaultParameterSetName = 'Switch')]
param(
    [Parameter(Mandatory = $true, Position = 0, ParameterSetName = 'Switch')]
    [ValidateSet('visakanbaskaran', 'krishnavaranan1', 'krishnavaranan', 'varananrp')]
    [string]$Workspace,
    [Parameter(Mandatory = $true, ParameterSetName = 'Status')]
    [switch]$Status,
    [Parameter(ParameterSetName = 'Switch')]
    [switch]$Preview,
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}$')]
    [string]$HostName = '15.134.177.14',
    [ValidatePattern('^[a-z_][a-z0-9_-]{0,31}$')]
    [string]$UserName = 'ubuntu',
    [string]$IdentityFile = (Join-Path $env:USERPROFILE '.ssh\voicelearn-ec2-20261013')
)
$ErrorActionPreference = 'Stop'
$destination = "$UserName@$HostName"
$statusCommand = 'sudo -n /opt/voicelearn/tools/bin/python /srv/voicelearn/current/deploy/ec2/modal-status.py'
$remoteCommand = if ($Status) { $statusCommand } else {
    "sudo -n bash /srv/voicelearn/current/deploy/ec2/switch-modal.sh $Workspace"
}
if ($Preview) {
    Write-Output "EC2: $destination"
    Write-Output "Remote command: $remoteCommand"
    Write-Output 'Preview only. No connection, inference or configuration change was made.'
    return
}
if (-not (Test-Path -LiteralPath $IdentityFile -PathType Leaf)) {
    throw 'EC2 SSH key was not found. Supply -IdentityFile with your existing private key path. Do not share or commit the key.'
}
$ssh = (Get-Command ssh.exe -ErrorAction Stop).Source
$keyPath = (Resolve-Path -LiteralPath $IdentityFile).Path
# Existing SSH trust is required; do not automatically accept a new host key.
$sshArguments = @('-T', '-i', $keyPath, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
    '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3', $destination)
if ($Status) {
    $selected = & $ssh @sshArguments $remoteCommand
    if ($LASTEXITCODE -ne 0) { throw 'Cloud status could not be read. Check your connection, SSH key and verified EC2 host trust.' }
    Write-Output $selected
    return
}
Write-Host "Switching hosted backend to $Workspace on $destination..."
Write-Host 'The server verifies models first, restarts the backend and checks health. Wait for completion.'
& $ssh @sshArguments $remoteCommand
if ($LASTEXITCODE -ne 0) {
    throw 'Cloud switch did not complete successfully. Do not assume the workspace changed; run -Status and inspect the server output.'
}
$selected = & $ssh @sshArguments $statusCommand
if ($LASTEXITCODE -ne 0 -or ($selected -join "`n").Trim() -ne "MODAL_WORKSPACE=$Workspace") {
    throw 'The switch returned, but the selected cloud workspace could not be confirmed. Run -Status before retrying.'
}
Write-Host "Cloud workspace confirmed: $Workspace. The frontend URL stays the same."
