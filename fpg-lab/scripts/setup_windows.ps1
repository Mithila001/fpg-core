[CmdletBinding()]
param(
    [ValidateSet("Yes", "No")]
    [string]$Fresh = "No"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VirtualEnvironment = Join-Path $RepositoryRoot ".venv"
$VirtualPython = Join-Path $VirtualEnvironment "Scripts\python.exe"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$Arguments
    )
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $Arguments"
    }
}

Push-Location $RepositoryRoot
try {
    $Launcher = $null
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $Launcher = "python"
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $Launcher = "py"
    }
    else {
        throw "Python 3.11 or newer was not found. Install Python, then rerun this script."
    }

    Invoke-Checked -Command $Launcher -Arguments @("-c", "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ is required'; print(sys.version)")

    if (-not (Test-Path -LiteralPath $VirtualPython)) {
        Invoke-Checked -Command $Launcher -Arguments @("-m", "venv", $VirtualEnvironment)
    }

    $ResolvedCorePath = (Resolve-Path (Join-Path $RepositoryRoot "..")).Path
    if (-not (Test-Path -LiteralPath (Join-Path $ResolvedCorePath "pyproject.toml"))) {
        throw "fpg-core was not found at $ResolvedCorePath"
    }

    Invoke-Checked -Command $VirtualPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Checked -Command $VirtualPython -Arguments @("-m", "pip", "install", "-e", $ResolvedCorePath, "-e", ".[dev]")

    if (-not (Test-Path -LiteralPath ".env")) {
        Copy-Item -LiteralPath ".env.example" -Destination ".env"
    }

    Invoke-Checked -Command $VirtualPython -Arguments @("-m", "scripts.verify_fpg_core")
    if ($Fresh -eq "Yes") {
        Invoke-Checked -Command $VirtualPython -Arguments @("-m", "scripts.lab_db", "reset", "--scope", "all", "--yes")
    } else {
        Invoke-Checked -Command $VirtualPython -Arguments @("-m", "scripts.lab_db", "migrate", "--json")
        Invoke-Checked -Command $VirtualPython -Arguments @("-m", "scripts.lab_db", "seed", "--json")
    }

    Write-Host ""
    Write-Host "FPG Lab initialization completed."
    Write-Host "Start the Lab with:"
    Write-Host ".\.venv\Scripts\python.exe run_lab.py"
}
finally {
    Pop-Location
}
