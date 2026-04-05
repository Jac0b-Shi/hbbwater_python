# 传感器测试数据快速发送工具

# 设置默认token（根据实际情况修改）
$TOKEN = "8b69faff1697440f"

function Show-Menu {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "  传感器测试数据快速发送工具" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. 发送正常状态数据"
    Write-Host "2. 发送浸水告警数据"
    Write-Host "3. 发送漏水场景序列"
    Write-Host "4. 发送浸水场景序列"
    Write-Host "5. 发送24小时历史数据（约288条）"
    Write-Host "6. 发送12小时历史数据（约144条）"
    Write-Host "0. 退出"
    Write-Host ""
}

function Test-Token {
    param([string]$Token)
    if ($Token -eq "YOUR_TOKEN_HERE") {
        Write-Host "错误: 请先修改脚本中的 TOKEN 变量！" -ForegroundColor Red
        Write-Host "请在传感器管理页面编辑传感器获取 webhook token。" -ForegroundColor Yellow
        exit 1
    }
}

# 检查 token
Test-Token -Token $TOKEN

# 检查 Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 未找到 Python，请确保已安装 Python 并添加到 PATH" -ForegroundColor Red
    exit 1
}

while ($true) {
    Show-Menu
    $choice = Read-Host "请输入选项 (0-6)"
    
    switch ($choice) {
        "1" {
            Write-Host "发送正常状态数据..." -ForegroundColor Green
            python send_test_data.py --token $TOKEN
        }
        "2" {
            Write-Host "发送浸水告警数据..." -ForegroundColor Yellow
            python send_test_data.py --token $TOKEN --detected --duration 600 --severity high --status danger
        }
        "3" {
            Write-Host "发送漏水场景..." -ForegroundColor Cyan
            python send_test_data.py --token $TOKEN --scenario leak
        }
        "4" {
            Write-Host "发送浸水场景..." -ForegroundColor Red
            python send_test_data.py --token $TOKEN --scenario flood
        }
        "5" {
            Write-Host "发送24小时历史数据（约288条）..." -ForegroundColor Magenta
            python send_test_data.py --token $TOKEN --history --hours 24
        }
        "6" {
            Write-Host "发送12小时历史数据（约144条）..." -ForegroundColor Magenta
            python send_test_data.py --token $TOKEN --history --hours 12
        }
        "0" {
            exit 0
        }
        default {
            Write-Host "无效选项，请重试" -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "操作完成！请在浏览器中查看数据。" -ForegroundColor Green
    Write-Host ""
    Read-Host "按 Enter 键继续"
}
