@echo off
chcp 65001 >nul
echo =========================================
echo  传感器测试数据快速发送工具
echo =========================================
echo.

:: 设置默认token（根据实际情况修改）
set TOKEN=8b69faff1697440f

echo 选择测试类型:
echo 1. 发送正常状态数据
echo 2. 发送浸水告警数据
echo 3. 发送漏水场景序列
echo 4. 发送浸水场景序列
echo 5. 发送24小时历史数据
echo 6. 发送12小时历史数据
echo.
set /p choice="请输入选项 (1-6): "

if "%choice%"=="1" (
    echo.
    echo 发送正常状态数据...
    python send_test_data.py --token %TOKEN%
)

if "%choice%"=="2" (
    echo.
    echo 发送浸水告警数据...
    python send_test_data.py --token %TOKEN% --detected --duration 600 --severity high --status danger
)

if "%choice%"=="3" (
    echo.
    echo 发送漏水场景...
    python send_test_data.py --token %TOKEN% --scenario leak
)

if "%choice%"=="4" (
    echo.
    echo 发送浸水场景...
    python send_test_data.py --token %TOKEN% --scenario flood
)

if "%choice%"=="5" (
    echo.
    echo 发送24小时历史数据（约288条）...
    python send_test_data.py --token %TOKEN% --history --hours 24
)

if "%choice%"=="6" (
    echo.
    echo 发送12小时历史数据（约144条）...
    python send_test_data.py --token %TOKEN% --history --hours 12
)

echo.
echo 发送完成！请在浏览器中查看数据。
pause
