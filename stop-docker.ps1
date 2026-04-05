#!/usr/bin/env pwsh
# 一键停止 Docker 环境 (Windows)

$PROJECT_DIR = $PSScriptRoot

# 颜色输出函数
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $foregroundColor
    if ($args) { Write-Output $args }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success { Write-ColorOutput Green $args }
function Write-Warning { Write-ColorOutput Yellow $args }
function Write-Info { Write-ColorOutput Cyan $args }

Write-Info "========================================"
Write-Info "  校园水浸监测系统 - Docker 停止脚本"
Write-Info "========================================"
Write-Output ""

# 检测 docker compose 命令
$dockerComposeCmd = "docker compose"
try {
    Invoke-Expression "$dockerComposeCmd version" | Out-Null
} catch {
    $dockerComposeCmd = "docker-compose"
}

Write-Info "正在停止服务..."
Write-Output ""

# 停止服务
try {
    Invoke-Expression "$dockerComposeCmd -f '$PROJECT_DIR\docker-compose.yml' down"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Output ""
        Write-Success "所有服务已停止"
    } else {
        Write-Warning "服务停止时出现问题"
    }
} catch {
    Write-Warning "停止出错: $_"
}

Write-Output ""
Write-Output "按任意键继续..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
