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

    if ($Fresh -eq "Yes") {
        Invoke-Checked -Command $VirtualPython -Arguments @("-m", "scripts.reset_db", "--yes")
    }

    Invoke-Checked -Command $VirtualPython -Arguments @("-m", "scripts.init_db")
    Invoke-Checked -Command $VirtualPython -Arguments @("-m", "scripts.verify_fpg_core", "--system-config", "seed/system_configuration.default.json")
    Invoke-Checked -Command $VirtualPython -Arguments @(
        "-m", "scripts.seed_db", "--system-config", "seed/system_configuration.default.json", "--activate",
        "--floor-plan-template", "seed/floor_plan_template.example.json",
        "--floor-plan-template", "seed/floor_plan_template.garage_veranda.json",
        "--floor-plan-template", "seed/floor_plan_template.two_bedroom_ensuite.json",
        "--floor-plan-template", "seed/floor_plan_template.three_bedroom_ensuites.json"
    )

    Write-Host ""
    Write-Host "FPG Lab initialization completed."
    Write-Host "Start the Lab with:"
    Write-Host ".\.venv\Scripts\python.exe -m fpg_lab"
}
finally {
    Pop-Location
}
