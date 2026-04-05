# 清理假传感器数据脚本
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  清理假传感器数据" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "警告：这将删除所有传感器及其历史数据！" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "输入 'yes' 确认清理"
if ($confirm -ne 'yes') {
    Write-Host "已取消" -ForegroundColor Gray
    exit
}

Write-Host ""
Write-Host "正在执行清理..." -ForegroundColor Cyan

$containerName = "flood-monitoring-mysql"
$sqlFile = "database/cleanup_fake_data.sql"

# 检查容器是否运行
$containerRunning = docker ps --format "{{.Names}}" | Select-String $containerName
if (-not $containerRunning) {
    Write-Host "错误：MySQL 容器未运行，请先启动 Docker Compose" -ForegroundColor Red
    exit 1
}

# 执行清理
Get-Content $sqlFile | docker exec -i $containerName mysql -uflood_user -pflood_monitoring_2025 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ 清理完成！所有假传感器已删除" -ForegroundColor Green
    Write-Host ""
    Write-Host "请刷新浏览器页面查看效果" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "❌ 清理失败" -ForegroundColor Red
}

Write-Host ""
Read-Host "按 Enter 键退出"
