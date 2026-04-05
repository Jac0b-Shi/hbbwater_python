# 校园水浸监测系统 - Vue 前端 Dockerfile
# 多阶段构建

# 阶段 1: 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app

# 复制 package.json 和 package-lock.json
COPY package*.json ./

# 安装依赖（构建阶段需要 devDependencies）
RUN npm install

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# 阶段 2: 生产阶段（使用 Caddy 托管静态文件）
FROM caddy:2-alpine

# 复制构建好的文件到 Caddy 的站点目录
COPY --from=builder /app/dist /srv

# 复制 Caddyfile
COPY Caddyfile /etc/caddy/Caddyfile

# 暴露端口
EXPOSE 80

# Caddy 默认命令
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
