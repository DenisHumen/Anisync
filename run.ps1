<#
  Anisync — one-shot dev launcher for Windows (PowerShell).

  Mirrors run.sh: bootstraps a local .venv on first run (installs deps +
  the package in editable mode) and then launches the GUI. Pass-through
  args go to `python -m anisync`.

  Usage:   .\run.ps1                # launch
           .\run.ps1 --some-flag    # forwarded to the app

  If script execution is blocked, run once:
      Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#>
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $Root

$Venv = Join-Path $Root ".venv"
$Py   = Join-Path $Venv "Scripts\python.exe"

# Pick a base interpreter for bootstrapping (prefer the py launcher).
function Get-BasePython {
    if (Get-Command py -ErrorAction SilentlyContinue) { return @("py", "-3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @("python") }
    throw "No Python found on PATH. Install Python 3.11+ first."
}

# ── bootstrap venv ────────────────────────────────────────────────────────────
if (-not (Test-Path $Py)) {
    Write-Host "[run.ps1] Creating virtualenv at $Venv"
    $base = Get-BasePython
    & $base[0] $base[1..($base.Count-1)] -m venv $Venv
    & $Py -m pip install --upgrade pip wheel
    if (Test-Path (Join-Path $Root "requirements.txt")) {
        & $Py -m pip install -r (Join-Path $Root "requirements.txt")
    }
    & $Py -m pip install -e $Root
}

# Quieten Qt's missing-font chatter, matching run.sh.
$env:QT_LOGGING_RULES = "qt.qpa.fonts.warning=false"

# ── run ───────────────────────────────────────────────────────────────────────
& $Py -m anisync @args
exit $LASTEXITCODE
