# 校园水浸监测系统 - Webhook 代理 Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY webhook_proxy.py .

# 暴露端口（TCP 和 UDP 共用）
EXPOSE 8080/tcp
EXPOSE 8080/udp

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.connect(('localhost', 8080)); s.close()" || exit 1

# 启动命令
CMD ["python", "webhook_proxy.py"]
