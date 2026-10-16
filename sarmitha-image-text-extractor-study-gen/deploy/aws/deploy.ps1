[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-z]{2}(-[a-z]+)+-[0-9]+$')][string]$Region,
    [Parameter(Mandatory)][ValidatePattern('^vpc-[a-f0-9]+$')][string]$VpcId,
    [Parameter(Mandatory)][ValidatePattern('^subnet-[a-f0-9]+$')][string]$SubnetId,
    [ValidatePattern('^[A-Za-z][A-Za-z0-9-]+$')][string]$StackName = 'sarmitha-ocr',
    [ValidatePattern('^/[A-Za-z0-9_./-]+$')][string]$EnvironmentParameter = '/sarmitha/production/environment',
    [ValidateSet('t3.micro', 't3.small', 't3.medium')][string]$InstanceType = 't3.small',
    [ValidateSet('compose.yaml', 'compose.ec2.yaml')][string]$ComposeFile = 'compose.yaml',
    [string]$Profile
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$awsOptions = @('--region', $Region, '--no-cli-pager')
if ($Profile) { $awsOptions += @('--profile', $Profile) }
function Invoke-Aws {
    param([string[]]$Arguments)
    $result = & aws @Arguments @awsOptions
    if ($LASTEXITCODE -ne 0) { throw "AWS command failed: $($Arguments[0]) $($Arguments[1])" }
    return $result
}
Invoke-Aws -Arguments @('sts', 'get-caller-identity')
Invoke-Aws -Arguments @('cloudformation', 'deploy', '--stack-name', $StackName,
    '--template-file', (Join-Path $PSScriptRoot 'ec2.yaml'), '--capabilities', 'CAPABILITY_IAM',
    '--parameter-overrides', "VpcId=$VpcId", "SubnetId=$SubnetId", "InstanceType=$InstanceType",
    "EnvironmentParameter=$EnvironmentParameter", '--no-fail-on-empty-changeset')
$stack = (Invoke-Aws -Arguments @('cloudformation', 'describe-stacks', '--stack-name', $StackName, '--output', 'json')) | ConvertFrom-Json
$outputs = @{}
$stack.Stacks[0].Outputs | ForEach-Object { $outputs[$_.OutputKey] = $_.OutputValue }
$instanceId = $outputs.InstanceId
$bucket = $outputs.ArtifactBucket
if ($instanceId -notmatch '^i-[a-f0-9]+$' -or $bucket -notmatch '^[a-z0-9.-]+$') { throw 'Unexpected stack output.' }
$taskTemp = Join-Path $projectRoot '.tmp'
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$archive = Join-Path $taskTemp 'sarmitha-deploy.tar.gz'
# Explicit allowlist: excludes credentials, models, dataset, virtualenv and other projects.
& tar -czf $archive --exclude=__pycache__ --exclude=*.pyc -C $projectRoot backend/app backend/main.py backend/requirements.txt backend/Dockerfile backend/.dockerignore deploy/compose.yaml deploy/Caddyfile deploy/compose.ec2.yaml deploy/Caddyfile.ec2
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
$artifactKey = 'deploy/' + [guid]::NewGuid().ToString() + '.tar.gz'
Invoke-Aws -Arguments @('s3', 'cp', $archive, "s3://$bucket/$artifactKey", '--only-show-errors')
$commands = @(
    'set -eu',
    'umask 077',
    'cloud-init status --wait',
    'mkdir -p /opt/sarmitha',
    "aws s3 cp s3://$bucket/$artifactKey /opt/sarmitha/deploy.tar.gz --region $Region --only-show-errors",
    'tar -xzf /opt/sarmitha/deploy.tar.gz -C /opt/sarmitha',
    "aws ssm get-parameter --name '$EnvironmentParameter' --with-decryption --query Parameter.Value --output text --region '$Region' > /opt/sarmitha/deploy/.env",
    'cd /opt/sarmitha/deploy',
    "docker compose -f $ComposeFile --env-file .env config --quiet",
    "docker compose -f $ComposeFile --env-file .env up -d --build --wait --wait-timeout 180",
    "docker compose -f $ComposeFile exec -T api python -c `"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=65)`""
)
$commandFile = Join-Path $taskTemp 'ssm-deploy.json'
$request = @{ DocumentName = 'AWS-RunShellScript'; InstanceIds = @($instanceId); Parameters = @{ commands = $commands; executionTimeout = @('1200') } }
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($commandFile, ($request | ConvertTo-Json -Depth 6), $utf8)
Write-Host "EC2 IP: $($outputs.PublicIp). Point your backend DNS A record here."
$agentDeadline = (Get-Date).AddMinutes(15)
do {
    $agents = (Invoke-Aws -Arguments @('ssm', 'describe-instance-information', '--filters', "Key=InstanceIds,Values=$instanceId", '--output', 'json')) | ConvertFrom-Json
    $online = @($agents.InstanceInformationList | Where-Object { $_.PingStatus -eq 'Online' }).Count -gt 0
    if ($online) { break }
    Write-Host 'Waiting for the EC2 Systems Manager agent...'
    Start-Sleep -Seconds 10
} while ((Get-Date) -lt $agentDeadline)
if (-not $online) { throw 'EC2 did not connect to SSM. Check subnet internet routing and the instance role.' }
$command = (Invoke-Aws -Arguments @('ssm', 'send-command', '--cli-input-json', "file://$commandFile", '--output', 'json')) | ConvertFrom-Json
$commandId = $command.Command.CommandId
$deadline = (Get-Date).AddMinutes(25)
do {
    Start-Sleep -Seconds 10
    $invocation = (Invoke-Aws -Arguments @('ssm', 'list-command-invocations', '--command-id', $commandId, '--details', '--output', 'json')) | ConvertFrom-Json
    $status = $invocation.CommandInvocations | Select-Object -First 1 -ExpandProperty Status
    Write-Host "Deployment status: $status"
    if ($status -in @('Success', 'Failed', 'Cancelled', 'TimedOut')) { break }
} while ((Get-Date) -lt $deadline)
if ($status -ne 'Success') { throw "Deployment did not succeed. Inspect SSM command $commandId in the AWS console." }
Write-Host 'Backend containers started and readiness passed. Verify HTTPS /api/ready after DNS resolves.'
