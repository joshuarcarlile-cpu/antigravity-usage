$RepoScript = Join-Path $PSScriptRoot "..\skills\usage\scripts\usage.py"
$PluginScript = Join-Path ($env:USERPROFILE ?? $env:HOME) ".gemini\config\plugins\antigravity-usage\skills\usage\scripts\usage.py"
$GlobalScript = Join-Path ($env:USERPROFILE ?? $env:HOME) ".gemini\config\skills\usage\scripts\usage.py"

$ScriptPath = if (Test-Path $RepoScript) { $RepoScript } elseif (Test-Path $PluginScript) { $PluginScript } else { $GlobalScript }

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Error: usage.py script not found."
    exit 1
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $ScriptPath @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $ScriptPath @args
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    & python3 $ScriptPath @args
} else {
    Write-Error "Error: Python was not found on PATH."
    exit 1
}
