@echo off
chcp 65001 >nul
echo =========================================
echo  清理假传感器数据
echo =========================================
echo.
echo 警告：这将删除所有传感器及其历史数据！
echo.
pause

echo.
echo 正在执行清理...
docker exec -i flood-monitoring-mysql mysql -uflood_user -pflood_monitoring_2025 < database\cleanup_fake_data.sql

echo.
if %ERRORLEVEL% == 0 (
    echo ✅ 清理完成！
) else (
    echo ❌ 清理失败，请检查 Docker 容器是否运行
)

pause
