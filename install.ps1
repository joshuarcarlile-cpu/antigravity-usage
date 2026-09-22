<#
.SYNOPSIS
    Installs the Antigravity /usage Telemetry Skill and CLI command.
.DESCRIPTION
    Installs as a global Antigravity Skill (~/.gemini/config/skills/usage)
    and places CLI wrappers in ~/.gemini/antigravity-ide/bin/ for universal terminal access.
    Adheres strictly to Joshua's Global Developer Preferences (-LiteralPath safety, zero duplications).
#>

[CmdletBinding()]
param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Installing Antigravity /usage Telemetry Engine " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$HomeDir = $env:USERPROFILE
if (-not $HomeDir) { $HomeDir = $env:HOME }

$SkillDir = Join-Path $HomeDir ".gemini\config\skills\usage"
$LegacyPluginDir = Join-Path $HomeDir ".gemini\config\plugins\antigravity-usage"
$TargetBinDirs = @(
    (Join-Path $HomeDir ".gemini\antigravity-ide\bin"),
    (Join-Path $HomeDir ".gemini\antigravity\bin"),
    (Join-Path $HomeDir ".local\bin")
)

# 0. Clean up legacy plugin directory to prevent duplicate skill discovery
if (Test-Path -LiteralPath $LegacyPluginDir) {
    Write-Host "-> Removing legacy plugin directory to prevent duplications..." -ForegroundColor Yellow
    Remove-Item -LiteralPath $LegacyPluginDir -Recurse -Force
}

# 1. Determine Source (Local or Remote)
$ScriptRoot = $PSScriptRoot
if ($ScriptRoot -and (Test-Path -LiteralPath (Join-Path $ScriptRoot "skills\usage\SKILL.md"))) {
    $LocalSkillSrc = Join-Path $ScriptRoot "skills\usage"
    if (Test-Path -LiteralPath $SkillDir) { Remove-Item -LiteralPath $SkillDir -Recurse -Force }

    if ($Dev) {
        Write-Host "-> Installing in DEVELOPER MODE (Directory Junction)..." -ForegroundColor Magenta
        New-Item -ItemType Junction -Path $SkillDir -Target $LocalSkillSrc | Out-Null
        Write-Host "-> Live junction linked: $SkillDir -> $LocalSkillSrc" -ForegroundColor Green
    } else {
        Write-Host "-> Installing from local repository..." -ForegroundColor Green
        [System.IO.Directory]::CreateDirectory($SkillDir) | Out-Null
        Get-ChildItem -LiteralPath $LocalSkillSrc | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $SkillDir -Recurse -Force
        }
    }

    $SrcBat = Join-Path $ScriptRoot "bin\usage.bat"
    $SrcPs1 = Join-Path $ScriptRoot "bin\usage.ps1"
} else {
    Write-Host "-> Downloading latest release from GitHub..." -ForegroundColor Green
    $RepoUrl = "https://github.com/joshuarcarlile-cpu/antigravity-usage/archive/refs/heads/main.zip"
    $ZipPath = Join-Path $env:TEMP "antigravity-usage.zip"
    Invoke-WebRequest -Uri $RepoUrl -OutFile $ZipPath
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $env:TEMP -Force
    $Extracted = Join-Path $env:TEMP "antigravity-usage-main"
    $ExtractedSkill = Join-Path $Extracted "skills\usage"

    if (Test-Path -LiteralPath $SkillDir) { Remove-Item -LiteralPath $SkillDir -Recurse -Force }
    [System.IO.Directory]::CreateDirectory($SkillDir) | Out-Null
    Get-ChildItem -LiteralPath $ExtractedSkill | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $SkillDir -Recurse -Force
    }

    $SrcBat = Join-Path $Extracted "bin\usage.bat"
    $SrcPs1 = Join-Path $Extracted "bin\usage.ps1"

    Remove-Item -LiteralPath $Extracted -Recurse -Force
    Remove-Item -LiteralPath $ZipPath -Force
}

# 2. Deploy CLI Wrappers
foreach ($bDir in $TargetBinDirs) {
    if (-not (Test-Path -LiteralPath $bDir)) {
        [System.IO.Directory]::CreateDirectory($bDir) | Out-Null
    }
    if (Test-Path -LiteralPath $SrcBat) { Copy-Item -LiteralPath $SrcBat -Destination $bDir -Force }
    if (Test-Path -LiteralPath $SrcPs1) { Copy-Item -LiteralPath $SrcPs1 -Destination $bDir -Force }
    Write-Host "-> CLI wrappers installed to $bDir" -ForegroundColor Green
}

# 3. Verify Python & Test Engine
$PythonCmd = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }

if ($PythonCmd) {
    Write-Host "-> Verifying installation..." -ForegroundColor Green
    $TestScript = Join-Path $SkillDir "tests\test_usage.py"
    if (Test-Path -LiteralPath $TestScript) {
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $res = & $PythonCmd.Split()[0] ($PythonCmd.Split()[1..$PythonCmd.Length] + @($TestScript)) 2>&1
        $testExit = $LASTEXITCODE
        $ErrorActionPreference = $prevEAP
        if ($testExit -eq 0) {
            Write-Host "-> All automated test invariants verified (PASS)!" -ForegroundColor Green
        } else {
            Write-Host "-> Warning: Some test invariants failed:" -ForegroundColor Yellow
            $res | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
        }
    }
}

Write-Host "`nInstallation Complete!" -ForegroundColor Green
Write-Host "You can now:" -ForegroundColor Cyan
Write-Host "  1. In any Antigravity chat, type: /usage or /cost" -ForegroundColor White
Write-Host "  2. In your terminal, run: usage (or usage --daily, usage --json)" -ForegroundColor White
