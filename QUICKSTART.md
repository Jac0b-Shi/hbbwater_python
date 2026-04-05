# 快速开始指南

## 环境要求

- **Docker** 20.10+
- **Docker Compose** 2.0+

## 启动项目

```bash
# Windows
.\start-docker.ps1

# Linux / macOS
./start-docker.sh
```

## 访问系统

- 🌐 **网站**: http://localhost
- 📚 **API 文档**: http://localhost:8000/docs

## 停止服务

```bash
# Windows
.\stop-docker.ps1

# Linux / macOS
./stop-docker.sh
```

## PhpStorm 一键启动

1. 打开 PhpStorm
2. 点击运行配置下拉菜单
3. 选择 **"⭐ Docker Start & Open Website"**
4. 点击 ▶️ 运行

## 重要文件

| 文件 | 用途 |
|------|------|
| `start-docker.ps1` / `.sh` | Docker 启动脚本 |
| `stop-docker.ps1` / `.sh` | Docker 停止脚本 |
| `docker-compose.yml` | Docker 服务编排 |
| `.env.docker` | 环境配置模板 |
| `DOCKER.md` | Docker 详细文档 |

## 常见问题

**Q: 端口被占用怎么办？**

A: 修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "8080:80"  # 将 80 改为其他端口如 8080
```

**Q: 如何修改数据库密码？**

A: 编辑 `.env` 文件（启动脚本会自动从 `.env.docker` 创建）：
```env
DB_PASSWORD=你的新密码
MYSQL_ROOT_PASSWORD=root新密码
```

**Q: 数据会丢失吗？**

A: 数据保存在 Docker Volume 中，重启不会丢失。如需完全清理，使用 `docker compose down -v`。

## 详细文档

查看 [DOCKER.md](DOCKER.md) 了解更多配置、故障排查和生产部署建议。
