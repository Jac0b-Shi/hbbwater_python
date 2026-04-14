param(
    [string]$WslDistro = "ubuntu-22.04",
    [string]$DmHome = "/opt/dmdbms",
    [string]$TargetRoot = "E:\CodeProjects\hbbwater\backend\vendor\dm"
)

$ErrorActionPreference = "Stop"

$sourceRoot = "\\wsl$\$WslDistro" + ($DmHome -replace "/", "\")

if (-not (Test-Path $sourceRoot)) {
    throw "WSL DM runtime path not found: $sourceRoot"
}

$requiredPaths = @(
    "bin\libdmdpi.so",
    "include\DPI.h",
    "include\DPIext.h",
    "include\DPItypes.h",
    "drivers\dpi\libdmdpi.so",
    "drivers\dpi\include\DPI.h",
    "drivers\dpi\include\DPIext.h",
    "drivers\dpi\include\DPItypes.h"
)

foreach ($relativePath in $requiredPaths) {
    $sourcePath = Join-Path $sourceRoot $relativePath
    if (-not (Test-Path $sourcePath)) {
        throw "Required DM runtime file not found: $sourcePath"
    }

    $targetPath = Join-Path $TargetRoot $relativePath
    $targetDir = Split-Path -Parent $targetPath
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Copy-Item -Force $sourcePath $targetPath
    Write-Host "Copied $relativePath"
}
