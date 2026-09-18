<#
.SYNOPSIS
    Installs the Antigravity /usage Telemetry Plugin and CLI command.
.DESCRIPTION
    Installs as a global Antigravity Plugin (~/.gemini/config/plugins/antigravity-usage)
    and places the CLI wrapper in ~/.gemini/antigravity-ide/bin/ for universal terminal access.
#>

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Installing Antigravity /usage Telemetry Engine " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$HomeDir = $env:USERPROFILE
if (-not $HomeDir) { $HomeDir = $env:HOME }

$PluginDir = Join-Path $HomeDir ".gemini\config\plugins\antigravity-usage"
$BinDir = Join-Path $HomeDir ".gemini\antigravity-ide\bin"

# 1. Determine Source (Local or Remote)
$ScriptRoot = $PSScriptRoot
if ($ScriptRoot -and (Test-Path (Join-Path $ScriptRoot "plugin.json"))) {
    Write-Host "-> Installing from local repository..." -ForegroundColor Green
    if (Test-Path $PluginDir) { Remove-Item -Recurse -Force $PluginDir }
    New-Item -ItemType Directory -Force -Path $PluginDir | Out-Null
    Copy-Item -Recurse -Force (Join-Path $ScriptRoot "*") $PluginDir
} else {
    Write-Host "-> Downloading latest release from GitHub..." -ForegroundColor Green
    $RepoUrl = "https://github.com/google-antigravity/antigravity-usage/archive/refs/heads/main.zip"
    $ZipPath = Join-Path $env:TEMP "antigravity-usage.zip"
    Invoke-WebRequest -Uri $RepoUrl -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath $env:TEMP -Force
    $Extracted = Join-Path $env:TEMP "antigravity-usage-main"
    if (Test-Path $PluginDir) { Remove-Item -Recurse -Force $PluginDir }
    Move-Item -Force $Extracted $PluginDir
    Remove-Item -Force $ZipPath
}

# 2. Deploy CLI Wrappers
if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
}

$SrcBat = Join-Path $PluginDir "bin\usage.bat"
$SrcPs1 = Join-Path $PluginDir "bin\usage.ps1"
if (Test-Path $SrcBat) { Copy-Item -Force $SrcBat $BinDir }
if (Test-Path $SrcPs1) { Copy-Item -Force $SrcPs1 $BinDir }

Write-Host "-> CLI wrappers installed to $BinDir" -ForegroundColor Green

# 3. Verify Python & Test Engine
$PythonCmd = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }

if ($PythonCmd) {
    Write-Host "-> Verifying installation..." -ForegroundColor Green
    $TestScript = Join-Path $PluginDir "skills\usage\tests\test_usage.py"
    if (Test-Path $TestScript) {
        $res = & $PythonCmd.Split()[0] ($PythonCmd.Split()[1..$PythonCmd.Length] + @($TestScript)) 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "-> All automated test invariants verified (PASS)!" -ForegroundColor Green
        }
    }
}

Write-Host "`nInstallation Complete!" -ForegroundColor Green
Write-Host "You can now:" -ForegroundColor Cyan
Write-Host "  1. In any Antigravity chat, type: /usage or /cost" -ForegroundColor White
Write-Host "  2. In your terminal, run: usage (or usage --daily, usage --json)" -ForegroundColor White
