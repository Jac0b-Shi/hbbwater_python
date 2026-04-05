#!/bin/bash
# 一键停止 Docker 环境 (Linux/macOS)

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  校园水浸监测系统 - Docker 停止脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检测 docker compose 命令
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo -e "${BLUE}正在停止服务...${NC}"
echo ""

if $COMPOSE_CMD -f "$PROJECT_DIR/docker-compose.yml" down; then
    echo ""
    echo -e "${GREEN}所有服务已停止${NC}"
else
    echo -e "${YELLOW}服务停止时出现问题${NC}"
fi
