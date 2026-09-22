$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $env:HOME }

# 1. Check if current working directory (or any ancestor) is the dev repo
$CwdScript = $null
$curr = (Get-Location).Path
while ($curr) {
    $candidateScript = Join-Path $curr "skills\usage\scripts\usage.py"
    $candidateManifest = Join-Path $curr "plugin.json"
    if ((Test-Path -LiteralPath $candidateScript) -and (Test-Path -LiteralPath $candidateManifest)) {
        $CwdScript = $candidateScript
        break
    }
    $parent = Split-Path -Parent $curr
    if (-not $parent -or $parent -eq $curr) { break }
    $curr = $parent
}

$RepoScript = Join-Path $PSScriptRoot "..\skills\usage\scripts\usage.py"
$GlobalScript = Join-Path $HomeDir ".gemini\config\skills\usage\scripts\usage.py"
$PluginScript = Join-Path $HomeDir ".gemini\config\plugins\antigravity-usage\skills\usage\scripts\usage.py"

$ScriptPath = if ($CwdScript -and (Test-Path -LiteralPath $CwdScript)) {
    $CwdScript
} elseif (Test-Path -LiteralPath $RepoScript) { 
    $RepoScript 
} elseif (Test-Path -LiteralPath $GlobalScript) { 
    $GlobalScript 
} elseif (Test-Path -LiteralPath $PluginScript) { 
    $PluginScript 
} else { 
    $null 
}

if (-not $ScriptPath -or -not (Test-Path -LiteralPath $ScriptPath)) {
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
