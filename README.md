# 校园水浸监测系统

校园水浸监测系统是一套面向园区、学校和地下空间的 IoT 防汛监测平台，用于接入超声波水位传感器和浸水传感器，完成数据采集、地图展示、阈值告警、通知推送和日常运维。

本版本采用 Python 技术栈实现业务服务、前端控制台、MQTT 接入和测试工具，默认以 Docker Compose 方式交付，适合在单台服务器或轻量级边缘网关上部署。

## 系统能力

- MQTT 设备接入：通过 `hbbwater/{device_type}/{device_id}/data` 订阅传感器数据
- HTTP 兼容入口：提供调试和第三方系统补录数据接口
- 水位地图：基于校园底图展示传感器点位、在线状态、最近读数和告警状态
- 传感器管理：支持新增、编辑、删除传感器，并展示 MQTT Topic 与示例上报报文
- 告警处理：支持超声波阈值、浸水状态、告警冷却和恢复自动解除
- 数据持久化：PostgreSQL 存储设备、读数、告警、用户和系统配置
- 可视化控制台：Streamlit 提供仪表盘、地图、传感器管理和告警管理页面
- 容器化部署：PostgreSQL、EMQX、FastAPI、Streamlit 四容器组合运行

## 部署拓扑

```text
现场传感器
  |
  | MQTT
  v
EMQX Broker (:1883)
  |
  | Python paho-mqtt subscriber
  v
FastAPI 后端 (:8000)
  |
  | SQLAlchemy async
  v
PostgreSQL
  ^
  |
Streamlit 运维控制台 (:8501)
```

## 服务清单

| 服务 | 默认端口 | 说明 |
|------|----------|------|
| `frontend` | `8501` | 运维控制台，提供仪表盘、水位地图、传感器和告警管理 |
| `backend` | `8000` | FastAPI 后端，提供 API、认证、告警和 MQTT 消费逻辑 |
| `emqx` | `1883`, `18083` | MQTT Broker 与 EMQX 管理控制台 |
| `postgres` | Docker 内网 | 业务数据库，默认不暴露宿主机端口 |

## 技术架构

系统按“接入层、业务层、持久化层、展示层”拆分，所有自研业务代码均使用 Python 实现。

| 分层 | 技术组件 | 主要职责 |
|------|----------|----------|
| 设备接入层 | EMQX, `paho-mqtt` | 接收现场传感器 MQTT 消息，后端后台线程订阅数据 Topic |
| API 与业务层 | FastAPI, Pydantic, SQLAlchemy Async | 提供 REST API、数据校验、传感器注册、读数入库和告警判断 |
| 数据层 | PostgreSQL 16 | 保存用户、传感器、读数、告警和系统配置 |
| 展示层 | Streamlit | 提供仪表盘、水位地图、点位维护、MQTT 绑定展示和告警处理 |
| 运维交付 | Docker Compose | 编排数据库、MQTT Broker、后端和前端，便于服务器部署 |

后端启动时会执行以下初始化流程：

1. 连接 PostgreSQL 并创建缺失表结构。
2. 根据 `.env` 中的管理员配置初始化默认账号。
3. 启动 Python MQTT 后台订阅线程。
4. 对外开放 `/health`、`/docs` 和 `/api/*` 接口。

传感器数据处理链路如下：

```text
设备 MQTT Publish
  -> EMQX
  -> backend MqttWorker
  -> parse_sensor_payload()
  -> get_or_create_sensor()
  -> sensor_readings 入库
  -> evaluate_status()
  -> alerts 创建或自动恢复
  -> Streamlit 控制台查询展示
```

HTTP 调试入口和 MQTT 入口共用同一套 `ingest_payload()` 业务逻辑，因此阈值判断、自动注册、告警冷却和通知行为保持一致。

## 环境要求

- Docker 20.10+
- Docker Compose v2+
- 服务器建议 2 核 CPU、4 GB 内存、20 GB 可用磁盘起步
- 生产环境建议准备反向代理、HTTPS 证书和独立备份目录

## 部署步骤

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

上线前至少修改以下配置：

```env
POSTGRES_PASSWORD=replace-with-strong-password
JWT_SECRET=replace-with-long-random-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-strong-admin-password
API_PORT=8000
FRONTEND_PORT=8501
MQTT_PORT=1883
EMQX_DASHBOARD_PORT=18083
```

启动服务：

```powershell
docker compose up -d --build
```

检查服务状态：

```powershell
docker compose ps
docker compose logs --tail=100 backend
```

访问入口：

- 运维控制台：http://localhost:8501
- API 文档：http://localhost:8000/docs
- MQTT Broker：`localhost:1883`
- EMQX Dashboard：http://localhost:18083

首次部署会自动创建管理员账号，默认值来自 `.env` 中的 `ADMIN_USERNAME` 与 `ADMIN_PASSWORD`。

## 设备接入

设备 Topic 约定：

```text
hbbwater/{device_type}/{device_id}/data
```

RDK X5 + L07A 超声传感器的现场复刻部署流程见 [docs/rdk-x5-ultrasonic-deployment.md](docs/rdk-x5-ultrasonic-deployment.md)。该流程默认由 RDK X5 通过 `/dev/ttyS2` 采集超声距离，并通过局域网或 Tailscale/Headscale 发布到本项目自带 EMQX Broker。

`device_type` 支持：

- `ultrasonic`：超声波水位传感器
- `immersion`：浸水传感器

超声波水位报文：

```json
{
  "device_id": "US001",
  "timestamp": "2026-05-02T12:30:00+00:00",
  "type": "ultrasonic",
  "value": 12.5,
  "unit": "cm",
  "battery": 85,
  "rssi": -65
}
```

浸水传感器报文：

```json
{
  "device_id": "IM001",
  "timestamp": "2026-05-02T12:30:00+00:00",
  "type": "immersion",
  "water_detected": true,
  "battery": 91,
  "rssi": -58
}
```

传感器可以先在控制台的“传感器管理”页面创建，也可以首次上报时由后端自动注册。生产接入建议先在控制台中录入点位、阈值、地图坐标和设备 ID，再将设备配置为对应 MQTT Topic。

### MQTT 字段兼容

后端解析器兼容以下字段别名，便于对接不同厂商的网关或固件：

| 业务字段 | 支持字段 | 说明 |
|----------|----------|------|
| 设备编号 | `device_id`, `deviceId`, `sensor_id`, Topic 中的 `{device_id}` | 必填，用于绑定传感器档案 |
| 传感器类型 | `type`, `sensor_type`, Topic 中的 `{device_type}` | 仅支持 `ultrasonic` 和 `immersion` |
| 水位值 | `value`, `water_level` | 超声波传感器必填 |
| 浸水状态 | `water_detected`, `value` | 浸水传感器会转换为 `1.0` 或 `0.0` |
| 单位 | `unit` | `mm` 会自动换算为 `cm`，布尔状态统一为 `state` |
| 电量 | `battery`, `battery_level` | 0 到 100 的整数 |
| 信号强度 | `rssi`, `signal_strength` | 一般为负数，单位按设备侧约定 |
| 时间戳 | `timestamp`, `created_at` | ISO 8601 字符串，缺省时使用后端接收时间 |

自动注册传感器的默认规则：

| 类型 | 默认位置 | 默认坐标 | 预警阈值 | 危险阈值 | 阈值方向 |
|------|----------|----------|----------|----------|----------|
| `ultrasonic` | `未配置位置` | `50, 50` | `10 cm` | `20 cm` | 大于等于触发 |
| `immersion` | `未配置位置` | `50, 50` | `1` | `1` | 大于等于触发 |

实际部署时建议不要依赖自动注册长期运行，应在控制台中补齐点位名称、地图坐标、阈值、上报间隔和告警间隔。

### HTTP 接入

HTTP 入口适合网关转发、第三方平台补录和现场联调：

```http
POST /api/ingest/http
Content-Type: application/json
```

```json
{
  "device_id": "US001",
  "type": "ultrasonic",
  "value": 18.2,
  "unit": "cm",
  "battery": 82,
  "rssi": -63
}
```

也可以使用设备编号路径写入：

```http
POST /api/sensors/US001/readings
Content-Type: application/json
```

请求体字段与 MQTT JSON 保持一致。

## 运维控制台

控制台默认包含四个页面：

- `仪表盘`：查看传感器数量、在线数量、活跃告警、今日读数和近期趋势
- `水位地图`：查看校园底图上的监测点位，编辑点位坐标和 MQTT 绑定信息
- `传感器管理`：新增、编辑、删除传感器，查看设备 Topic 与示例 JSON
- `告警管理`：查看告警列表，手动解除活跃告警

左侧“Python 数据模拟”用于现场调试或演示，会通过 HTTP 入口写入同一套接入逻辑。真实设备建议直接通过 MQTT 上报。

## API 接口清单

FastAPI 自动生成 OpenAPI 文档，部署后可访问 `http://localhost:8000/docs`。核心接口如下：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 服务健康检查，Docker healthcheck 使用该接口 |
| `POST` | `/api/auth/login` | 登录并返回 Bearer Token |
| `POST` | `/api/auth/register` | 注册用户，首个用户自动成为 `super_admin` |
| `GET` | `/api/account/me` | 查看当前账号信息 |
| `GET` | `/api/sensors` | 查询传感器列表，可通过 `type` 过滤 |
| `POST` | `/api/sensors` | 新增传感器并建立设备 ID 与 MQTT Topic 的绑定关系 |
| `GET` | `/api/sensors/{sensor_id}` | 查看单个传感器 |
| `PUT` | `/api/sensors/{sensor_id}` | 修改名称、位置、坐标、阈值、启用状态等信息 |
| `DELETE` | `/api/sensors/{sensor_id}` | 删除传感器，关联读数和告警会级联删除 |
| `GET` | `/api/sensors/{sensor_id}/readings` | 查看单个传感器历史读数 |
| `POST` | `/api/sensors/{device_id}/readings` | 按设备编号写入读数 |
| `POST` | `/api/ingest/http` | 通用 HTTP 数据接入 |
| `GET` | `/api/readings/recent` | 查询最近读数 |
| `GET` | `/api/alerts` | 查询告警列表，可通过 `status` 过滤 |
| `PUT` | `/api/alerts/{alert_id}/resolve` | 手动解除告警 |
| `GET` | `/api/alerts/stats` | 查询告警统计 |
| `GET` | `/api/dashboard/stats` | 仪表盘统计卡片数据 |
| `GET` | `/api/dashboard/sensor-status` | 地图和状态列表使用的实时点位数据 |
| `GET` | `/api/config` | 查询系统配置 |
| `PUT` | `/api/config` | 新增或更新系统配置 |
| `POST` | `/api/config/maintenance` | 运维检查接口，返回可归档读数数量 |

认证接口使用 JWT，令牌默认有效期为 `ACCESS_TOKEN_MINUTES=720` 分钟。当前 Streamlit 控制台面向内网部署场景，生产环境建议在反向代理层增加统一登录、IP 白名单或 VPN 访问控制。

## 数据模型

数据库采用 SQLAlchemy ORM 管理，核心表结构如下：

| 表 | 关键字段 | 说明 |
|----|----------|------|
| `users` | `username`, `password_hash`, `role`, `is_active` | 控制台用户和管理员账号 |
| `sensors` | `device_id`, `type`, `location`, `map_x`, `map_y`, `threshold_warn`, `threshold_danger`, `last_value`, `last_seen_at` | 传感器档案、地图点位、阈值和最近状态 |
| `sensor_readings` | `sensor_id`, `value`, `unit`, `battery`, `rssi`, `status`, `raw_json`, `created_at` | 传感器读数明细，保留原始 JSON 便于追溯 |
| `alerts` | `sensor_id`, `type`, `severity`, `message`, `status`, `triggered_at`, `resolved_at`, `cooldown_until` | 告警记录、冷却时间和解除状态 |
| `system_config` | `key`, `value`, `updated_at` | JSON 格式的运行配置 |

`sensor_readings` 对 `sensor_id, created_at` 建立联合索引，用于地图和历史读数查询。删除传感器时，其读数和告警通过外键级联删除。

## 告警规则

系统在每次读数入库后立即计算状态：

| 传感器类型 | 正常条件 | 预警条件 | 危险或告警条件 |
|------------|----------|----------|----------------|
| `ultrasonic` | 未达到阈值 | 触发 `threshold_warn` | 触发 `threshold_danger` |
| `immersion` | `water_detected=false` 或 `value=0` | 同危险条件 | `water_detected=true` 或 `value>=1` |

阈值方向由 `threshold_dir` 控制：

- `greater_or_equal`：读数大于等于阈值时触发，适合水位上涨类场景
- `less_or_equal`：读数小于等于阈值时触发，适合水位距离探头越近数值越小的设备

告警状态与恢复规则：

- 超声波预警生成 `high_water` 告警，严重级别为 `medium` 或 `high`
- 浸水触发生成 `water_detected` 告警，严重级别为 `critical`
- 同一传感器同一告警类型已有活跃告警时，只更新严重级别、消息和冷却时间
- 读数恢复正常后，当前传感器的活跃告警会自动标记为 `resolved`
- `ALERT_COOLDOWN_MINUTES` 用于限制重复告警创建频率，默认 30 分钟

如果配置了 `WEBHOOK_URL`，系统会向该地址发送文本告警 JSON；如果配置了 SMTP 和 `NOTIFY_EMAIL_TO`，系统会发送邮件告警。

## 运行配置

`.env` 支持以下主要配置项：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `POSTGRES_DB` | `hbbwater` | PostgreSQL 数据库名 |
| `POSTGRES_USER` | `hbbwater` | PostgreSQL 用户 |
| `POSTGRES_PASSWORD` | `hbbwater` | PostgreSQL 密码，生产必须修改 |
| `JWT_SECRET` | `replace-with-a-long-random-secret` | JWT 签名密钥，生产必须修改 |
| `ADMIN_USERNAME` | `admin` | 首次初始化管理员用户名 |
| `ADMIN_PASSWORD` | `admin123456` | 首次初始化管理员密码，生产必须修改 |
| `API_PORT` | `8000` | 后端宿主机端口 |
| `FRONTEND_PORT` | `8501` | Streamlit 控制台宿主机端口 |
| `MQTT_PORT` | `1883` | MQTT Broker 宿主机端口 |
| `EMQX_DASHBOARD_PORT` | `18083` | EMQX 管理控制台端口 |
| `ALERT_COOLDOWN_MINUTES` | `30` | 重复告警冷却时间 |
| `OFFLINE_TIMEOUT_SECONDS` | `300` | 地图在线状态判定窗口 |
| `WEBHOOK_URL` | 空 | 告警 Webhook 地址 |
| `SMTP_HOST` 等 SMTP 项 | 空 | 邮件告警配置 |

后端还支持 `MQTT_HOST`、`MQTT_USERNAME`、`MQTT_PASSWORD`、`MQTT_DATA_TOPIC`、`MQTT_STATUS_TOPIC` 等运行变量。Docker Compose 默认将后端连接到内部 `emqx:1883`，如接入外部 Broker，可在 Compose 或服务器环境变量中覆盖这些值。

## 常用运维命令

查看容器：

```powershell
docker compose ps
```

查看后端日志：

```powershell
docker compose logs -f backend
```

重启后端或前端：

```powershell
docker compose up -d --build backend frontend
```

停止服务：

```powershell
docker compose down
```

备份 PostgreSQL 数据：

```powershell
docker compose exec -T postgres pg_dump -U hbbwater hbbwater > hbbwater-backup.sql
```

恢复 PostgreSQL 数据：

```powershell
Get-Content hbbwater-backup.sql | docker compose exec -T postgres psql -U hbbwater hbbwater
```

查看健康状态：

```powershell
Invoke-RestMethod http://localhost:8000/health
```

执行一次维护检查：

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/config/maintenance
```

滚动更新后端和前端：

```powershell
docker compose build backend frontend
docker compose up -d backend frontend
docker compose ps
```

## 安全建议

- 生产环境必须修改 `.env` 中的数据库密码、管理员密码和 `JWT_SECRET`
- 不建议直接暴露 `8000`、`8501`、`18083` 到公网，应放在反向代理和访问控制之后
- MQTT 建议启用账号认证和 TLS，当前 Compose 文件保留为便于本地部署的基础配置
- 定期备份 PostgreSQL volume，并保留升级前镜像版本
- 告警 Webhook、SMTP 密码等敏感配置只写入 `.env`，不要提交到仓库

## 生产部署建议

- 建议使用 Nginx、Caddy 或网关产品统一代理 `frontend` 和 `backend`，并启用 HTTPS
- 外部设备接入 MQTT 时建议使用独立账号、Topic ACL 和 TLS 证书
- PostgreSQL volume 建议挂载到服务器数据盘，并纳入定期离线备份
- 升级前先执行 `pg_dump`，再更新镜像并重启 `backend`、`frontend`
- EMQX Dashboard 不建议暴露到公网，必要时只允许运维网段访问
- 大规模点位场景可将 `sensor_readings` 按时间归档，或通过 `/api/config/maintenance` 结果制定归档任务

## 本地开发与验证

核心业务单测不依赖 Docker：

```powershell
python -m unittest discover -s tests
```

模拟 MQTT 上报：

```powershell
python tools\publish_sample.py --host localhost --device-id US001 --type ultrasonic --value 23.5
python tools\publish_sample.py --host localhost --device-id IM001 --type immersion --value 1
```

主要测试覆盖：

- MQTT topic 与 payload 解析
- `mm` 到 `cm` 的单位归一化
- 浸水布尔值到状态读数的转换
- 水位阈值和浸水告警判定

## 目录结构

```text
.
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 路由和依赖
│   │   ├── mqtt/         # paho-mqtt 后台订阅
│   │   ├── services/     # 传感器接入、告警、认证和通知逻辑
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app.py            # Streamlit 运维控制台
│   ├── assets/           # 地图和静态资源
│   ├── Dockerfile
│   └── requirements.txt
├── tools/
│   └── publish_sample.py # Python MQTT 设备模拟器
├── tests/
│   └── test_core.py
├── .env.example
├── docker-compose.yml
├── LICENSE
└── README.md
```

## 许可证

本项目基于 GNU Lesser General Public License v3.0 开源，详见 [LICENSE](LICENSE)。
