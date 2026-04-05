#!/bin/bash
# 清理假传感器数据脚本

echo "========================================="
echo "  清理假传感器数据"
echo "========================================="
echo ""
echo "警告：这将删除所有传感器及其历史数据！"
echo ""
read -p "输入 'yes' 确认清理: " confirm
if [ "$confirm" != "yes" ]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "正在执行清理..."

CONTAINER_NAME="flood-monitoring-mysql"
SQL_FILE="database/cleanup_fake_data.sql"

# 检查容器是否运行
if ! docker ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "错误：MySQL 容器未运行，请先启动 Docker Compose"
    exit 1
fi

# 执行清理
docker exec -i "$CONTAINER_NAME" mysql -uflood_user -pflood_monitoring_2025 < "$SQL_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 清理完成！所有假传感器已删除"
    echo ""
    echo "请刷新浏览器页面查看效果"
else
    echo ""
    echo "❌ 清理失败"
fi
