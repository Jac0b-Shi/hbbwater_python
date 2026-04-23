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

$runtimeFiles = @(
    @{ Source = "bin\libdmdpi.so"; Target = "bin\libdmdpi.so" },
    @{ Source = "include\DPI.h"; Target = "include\DPI.h" },
    @{ Source = "include\DPIext.h"; Target = "include\DPIext.h" },
    @{ Source = "include\DPItypes.h"; Target = "include\DPItypes.h" },
    @{ Source = "drivers\dpi\libdmdpi.so"; Target = "drivers\dpi\libdmdpi.so" },
    @{ Source = "drivers\dpi\include\DPI.h"; Target = "drivers\dpi\include\DPI.h" },
    @{ Source = "drivers\dpi\include\DPIext.h"; Target = "drivers\dpi\include\DPIext.h" },
    @{ Source = "drivers\dpi\include\DPItypes.h"; Target = "drivers\dpi\include\DPItypes.h" },
    @{ Source = "bin\dependencies\libcrypto.so"; Target = "bin\libcrypto.so" },
    @{ Source = "bin\dependencies\libssl.so"; Target = "bin\libssl.so" },
    @{ Source = "bin\dependencies\libz.so"; Target = "bin\libz.so" },
    @{ Source = "bin\dependencies\libsnappy.so"; Target = "bin\libsnappy.so" },
    @{ Source = "bin\libdmgmssl.so"; Target = "bin\libdmgmssl.so" },
    @{ Source = "bin\libdmutl.so"; Target = "bin\libdmutl.so" },
    @{ Source = "bin\libdmos.so"; Target = "bin\libdmos.so" },
    @{ Source = "bin\libdmelog.so"; Target = "bin\libdmelog.so" },
    @{ Source = "bin\libdmcrypt.so"; Target = "bin\libdmcrypt.so" },
    @{ Source = "bin\libdmcvt.so"; Target = "bin\libdmcvt.so" }
)

foreach ($runtimeFile in $runtimeFiles) {
    $sourcePath = Join-Path $sourceRoot $runtimeFile.Source
    if (-not (Test-Path $sourcePath)) {
        throw "Required DM runtime file not found: $sourcePath"
    }

    $targetPath = Join-Path $TargetRoot $runtimeFile.Target
    $targetDir = Split-Path -Parent $targetPath
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Copy-Item -Force $sourcePath $targetPath
    Write-Host "Copied $($runtimeFile.Source) -> $($runtimeFile.Target)"
}
