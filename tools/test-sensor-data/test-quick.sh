#!/bin/bash
# 传感器测试数据快速发送工具

# 设置默认token（根据实际情况修改）
TOKEN="8b69faff1697440f"

show_menu() {
    echo ""
    echo "========================================="
    echo "  传感器测试数据快速发送工具"
    echo "========================================="
    echo ""
    echo "1. 发送正常状态数据"
    echo "2. 发送浸水告警数据"
    echo "3. 发送漏水场景序列"
    echo "4. 发送浸水场景序列"
    echo "5. 发送24小时历史数据（约288条）"
    echo "6. 发送12小时历史数据（约144条）"
    echo "0. 退出"
    echo ""
}

while true; do
    show_menu
    read -p "请输入选项 (0-6): " choice
    
    case $choice in
        1)
            echo "发送正常状态数据..."
            python3 send_test_data.py --token $TOKEN
            ;;
        2)
            echo "发送浸水告警数据..."
            python3 send_test_data.py --token $TOKEN --detected --duration 600 --severity high --status danger
            ;;
        3)
            echo "发送漏水场景..."
            python3 send_test_data.py --token $TOKEN --scenario leak
            ;;
        4)
            echo "发送浸水场景..."
            python3 send_test_data.py --token $TOKEN --scenario flood
            ;;
        5)
            echo "发送24小时历史数据（约288条）..."
            python3 send_test_data.py --token $TOKEN --history --hours 24
            ;;
        6)
            echo "发送12小时历史数据（约144条）..."
            python3 send_test_data.py --token $TOKEN --history --hours 12
            ;;
        0)
            exit 0
            ;;
        *)
            echo "无效选项，请重试"
            ;;
    esac
    
    echo ""
    echo "操作完成！请在浏览器中查看数据。"
    read -p "按 Enter 键继续"
done
