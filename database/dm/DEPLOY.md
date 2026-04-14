# DM8 Test Environment

本地 DM8 测试环境建议按独立测试实例维护，以下内容使用占位符示例：

- 实例目录：`D:\dmdata\YOUR_DB`
- 监听地址：`127.0.0.1:5236`
- 业务用户：`YOUR_APP_USER`
- 业务密码：`ChangeMe_123!`
- 当前启动方式：直接运行 `dmserver.exe D:\dmdata\YOUR_DB\dm.ini`

## Start

当前未注册 Windows 服务，重启后需手动启动：

```powershell
Start-Process -FilePath "D:\Program Files\dmdbms\bin\dmserver.exe" -ArgumentList "D:\dmdata\YOUR_DB\dm.ini"
```

确认端口监听：

```powershell
netstat -ano | Select-String ":5236"
```

确认数据库可连接：

```powershell
& "D:\Program Files\dmdbms\bin\DIsql.exe" 'YOUR_APP_USER/"ChangeMe_123!"@127.0.0.1:5236'
```

## Python Drivers

达梦 Python 驱动源码已随安装包提供：

- `D:\Program Files\dmdbms\drivers\python\dmPython`
- `D:\Program Files\dmdbms\drivers\python\dmAsync`
- `D:\Program Files\dmdbms\drivers\python\dmSQLAlchemy\dmSQLAlchemy2.0`

推荐安装顺序：

```powershell
$env:DM_HOME = "D:\Program Files\dmdbms"
.\backend\scripts\install_dm_drivers.ps1
```

如果你已经拿到了单独的达梦 Python 源码目录，例如仓库内的 `backend\达梦 Python 接口源码-20260401\python`，也可以显式指定：

```powershell
$env:DM_HOME = "D:\Program Files\dmdbms"
$env:DM_PYTHON_SOURCE_ROOT = "E:\CodeProjects\hbbwater\backend\达梦 Python 接口源码-20260401"
.\backend\scripts\install_dm_drivers.ps1
```

Ubuntu 主机可改用：

```bash
export DM_HOME=/opt/dmdbms
export DM_PYTHON_SOURCE_ROOT=$PWD/backend/达梦\ Python\ 接口源码-20260401
./backend/scripts/install_dm_drivers.sh
```

如果你的 Linux DM8 运行时已经装在本机 WSL，例如 `\\wsl$\ubuntu-22.04\opt\dmdbms`，可以先把最小运行时同步到仓库：

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\sync_dm_runtime_from_wsl.ps1
```

该脚本会把以下文件复制到 `backend/vendor/dm/`：
- `bin/libdmdpi.so`
- `include/DPI*.h`
- `drivers/dpi/libdmdpi.so`
- `drivers/dpi/include/DPI*.h`

如果需要手工执行：

```powershell
python -m pip install --user "D:\Program Files\dmdbms\drivers\python\dmPython"
python -m pip install --user "D:\Program Files\dmdbms\drivers\python\dmAsync"
python -m pip install --user "D:\Program Files\dmdbms\drivers\python\dmSQLAlchemy\dmSQLAlchemy2.0"
```

## Backend Config

后端建议优先使用结构化配置。

原因：
- 如果密码包含 `@` 等特殊字符，手写 `DATABASE_URL` 很容易因为未转义而解析错误。

结构化配置（单实例直连）：

```env
DM_HOME=D:\Program Files\dmdbms
DB_DIALECT=dm
DB_DRIVER=dmAsync
DB_HOST=127.0.0.1
DB_PORT=5236
DB_NAME=YOUR_DB
DB_USER=YOUR_APP_USER
DB_PASSWORD=ChangeMe_123!
```

结构化配置（服务名 / 高可用集群）：

```env
DM_HOME=D:\Program Files\dmdbms
DB_DIALECT=dm
DB_DRIVER=dmAsync
DB_SERVICE_NAME=DM_CLUSTER
DM_SVC_PATH=C:\Windows\System32
DB_NAME=YOUR_DB
DB_USER=YOUR_APP_USER
DB_PASSWORD=ChangeMe_123!
AUTO_CREATE_SCHEMA=false
```

如果单位下发的是服务名方式，需要先准备 `dm_svc.conf`。以下使用脱敏示例 `DM_CLUSTER`：

```ini
TIME_ZONE=(480)
LANGUAGE=(cn)
DM_CLUSTER=(192.0.2.10:5236,192.0.2.11:5237)
[DM_CLUSTER]
TIME_ZONE=(+480)
LOGIN_MODE=(1)
SWITCH_TIME=(3)
SWITCH_INTERVAL=(200)
```

说明：
- Windows 默认把 `dm_svc.conf` 放到 `%SystemRoot%\\System32`，并将 `DM_SVC_PATH` 指向该目录。
- Linux 默认放到 `/etc`，也可以把 `DM_SVC_PATH` 指向自定义目录。
- 本仓库后端已支持 `DB_SERVICE_NAME` 和 `DM_SVC_PATH`，容器内可通过 `BACKEND_DB_SERVICE_NAME` / `BACKEND_DM_SVC_PATH` 传入。
- 控制库默认建议使用 `BACKEND_CONTROL_DATABASE_URL=sqlite+aiosqlite:////app/runtime/control.db`，并挂载到 Docker volume。
- 若使用容器方式，可基于 `backend/Dockerfile.dm` 构建自定义镜像；构建前需先把 Linux 版 DM 客户端文件放入 `backend/vendor/dm/`。Python 包源码可直接使用仓库里的 `backend/达梦 Python 接口源码-20260401/python`。
- 仓库里的 `backend/达梦 PHP_PDO 接口源码-20260401/php_pdo` 属于 PHP 扩展，目前这套架构下不参与 backend 连接达梦；只有未来要让 WordPress/PHP 直接访问 DM 时才需要单独做 WordPress 自定义镜像。

如果必须使用连接串，密码中的特殊字符必须编码：

```env
DATABASE_URL=dm+dmAsync://YOUR_APP_USER:ChangeMe_123%21@127.0.0.1:5236/YOUR_DB
```

服务名模式下的连接串示例：

```env
DATABASE_URL=dm+dmAsync://YOUR_APP_USER:ChangeMe_123%21@DM_CLUSTER/YOUR_DB
```

## Notes

- 达梦脚本入口：`database/dm/init.sql`
- 测试环境引导脚本：`database/dm/bootstrap-test-env.sql`
- 本次实跑修复记录：`database/dm/repair-test-env.sql`
- 应用启动时默认不会替达梦自动建基础表；空库必须先执行 `database/dm/init.sql`
- 目前数据库侧 JOB 尚未迁移，维护任务仍建议由应用层触发。
