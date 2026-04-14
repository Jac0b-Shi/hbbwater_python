param(
    [string]$DmHome = $env:DM_HOME,
    [string]$PythonSourceRoot = $env:DM_PYTHON_SOURCE_ROOT
)

$ErrorActionPreference = "Stop"

if (-not $DmHome) {
    throw "DM_HOME is not set. Set DM_HOME to the DM8 installation directory first."
}

if (-not $PythonSourceRoot) {
    $PythonSourceRoot = Join-Path $DmHome "drivers\python"
}

if (Test-Path (Join-Path $PythonSourceRoot "python")) {
    $PythonSourceRoot = Join-Path $PythonSourceRoot "python"
}

$runtimeCandidates = @(
    (Join-Path $DmHome "dmdpi.dll"),
    (Join-Path $DmHome "bin\dmdpi.dll"),
    (Join-Path $DmHome "dpi\dmdpi.dll"),
    (Join-Path $DmHome "drivers\dpi\dmdpi.dll")
)
$runtimeFound = $runtimeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $runtimeFound) {
    throw "DM runtime library dmdpi.dll not found under $DmHome. Set DM_HOME to a full DM installation/runtime directory."
}

$includeCandidates = @(
    (Join-Path $DmHome "include"),
    (Join-Path $DmHome "dpi\include"),
    (Join-Path $DmHome "dpi\src\include"),
    (Join-Path $DmHome "drivers\python\dmPython")
)
$includeFound = $includeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $includeFound) {
    throw "DM include headers not found under $DmHome. dmPython build requires include or dpi/include."
}

$packages = @(
    (Join-Path $PythonSourceRoot "dmPython"),
    (Join-Path $PythonSourceRoot "dmAsync"),
    (Join-Path $PythonSourceRoot "dmSQLAlchemy\dmSQLAlchemy2.0")
)

foreach ($package in $packages) {
    if (-not (Test-Path $package)) {
        throw "Driver package not found: $package"
    }

    Write-Host "Installing $package"
    python -m pip install --user $package
}
