# 校园水浸监测系统 - Caddy 反向代理 Dockerfile
FROM caddy:2-alpine

# 复制 Caddyfile
COPY Caddyfile.docker /etc/caddy/Caddyfile

# 暴露端口
EXPOSE 80
EXPOSE 8000

# Caddy 默认命令
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
