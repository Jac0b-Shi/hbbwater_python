# 校园水浸监测系统 - 纯 Python/MQTT 版

这是面向“智能制造中的软件设计”课程的校园 IoT 水浸监测系统。项目来自原 `hbbwater` 的业务思路，但当前实现重建为纯 Python 栈：FastAPI 后端、Streamlit 前端、SQLAlchemy/PostgreSQL 数据库、paho-mqtt 接入 EMQX Broker。

老师要求必须使用 Python，并建议用 MQTT 替代 UDP；因此本仓库把能用 Python 实现的部分全部改成 Python。不可避免保留的非 Python 文件只有 Dockerfile、Compose YAML、环境变量样例和文档。

## 项目定位

系统面向校园场景，从超声波水位传感器和浸水传感器采集数据，经 MQTT 上报到 Broker，由后端订阅并写入数据库，再提供可视化仪表盘、地图、历史读数、告警和通知能力。

## 核心能力

- 多协议数据接入：MQTT 为主，HTTP 上报作为调试和兼容入口
- 两类传感器：超声波水位传感器、浸水二值传感器
- 数据库存储：PostgreSQL 保存传感器、读数、告警、系统配置和用户
- 告警引擎：阈值判断、告警冷却、恢复正常后自动解除
- 可视化前端：Streamlit 仪表盘、传感器状态表、Plotly 历史曲线、水位地图、告警处置
- Docker 部署：PostgreSQL + EMQX + FastAPI + Streamlit 四容器一键启动

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Streamlit, Plotly, pandas, requests |
| 后端 | FastAPI, SQLAlchemy 2.0 async, Pydantic v2 |
| 数据库 | PostgreSQL, asyncpg |
| MQTT | EMQX, paho-mqtt |
| 认证 | PyJWT, passlib/bcrypt |
| 通知 | Python smtplib, httpx webhook |
| 部署 | Docker Compose |

## 架构

```text
传感器
  |
  | MQTT: hbbwater/{device_type}/{device_id}/data
  v
EMQX Broker (:1883)
  |
  | Python paho-mqtt subscriber
  v
FastAPI backend (:8000)
  |
  | SQLAlchemy async
  v
PostgreSQL
  ^
  |
Streamlit frontend (:8501)
```

## 快速启动

复制环境变量样例后启动：

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

访问：

- Streamlit 前端：http://localhost:8501
- FastAPI 文档：http://localhost:8000/docs
- EMQX Dashboard：http://localhost:18083
- MQTT Broker：localhost:1883

默认管理员：

- 用户名：`admin`
- 密码：`admin123456`

## MQTT Topic 与消息格式

Topic：

```text
hbbwater/{device_type}/{device_id}/data
```

示例：

```text
hbbwater/ultrasonic/US001/data
hbbwater/immersion/IM001/data
```

超声波水位消息：

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

浸水传感器消息：

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

## Python 模拟上报

启动 Docker 服务后，可以用 Python 脚本模拟真实 MQTT 设备：

```powershell
python tools\publish_sample.py --host localhost --device-id US001 --type ultrasonic --value 23.5
python tools\publish_sample.py --host localhost --device-id IM001 --type immersion --value 1
```

也可以直接在 Streamlit 左侧使用“Python 数据模拟”，它通过 HTTP 入口写入同一套 Python 接入逻辑。

## 前端操作说明

Streamlit 前端已按原 `hbbwater` 的主要工作流组织：

- `水位地图`：展示状态卡片、校园底图、彩色传感器点位、点位标签和图例。选择点位后可编辑地图百分比坐标、锁定点位，并查看该点位的 MQTT Topic 与示例 JSON。
- `传感器管理`：可以新增、编辑、删除传感器。新增时填写设备 ID、类型、安装位置、阈值和地图坐标；页面会同步展示该设备应发布的 MQTT Topic。
- MQTT 绑定规则：设备发布到 `hbbwater/{device_type}/{device_id}/data`，其中 `device_id` 与传感器管理页的设备 ID 一致即可完成绑定。未预创建的设备也会在首次上报时自动注册。

## API 端点

认证：

- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/account/me`

传感器：

- `GET /api/sensors`
- `POST /api/sensors`
- `GET /api/sensors/{sensor_id}`
- `PUT /api/sensors/{sensor_id}`
- `DELETE /api/sensors/{sensor_id}`
- `GET /api/sensors/{sensor_id}/readings`
- `POST /api/sensors/{device_id}/readings`

数据接入与仪表盘：

- `POST /api/ingest/http`
- `GET /api/readings/recent`
- `GET /api/dashboard/stats`
- `GET /api/dashboard/sensor-status`

告警：

- `GET /api/alerts`
- `GET /api/alerts/stats`
- `PUT /api/alerts/{alert_id}/resolve`

系统配置：

- `GET /api/config`
- `PUT /api/config`
- `POST /api/config/maintenance`

## 本地测试

不依赖数据库和 Docker 的核心业务单测：

```powershell
python -m unittest discover -s tests
```

主要覆盖：

- MQTT topic + payload 解析
- `mm` 到 `cm` 的单位归一化
- 浸水布尔值到状态读数的转换
- 水位阈值和浸水告警判定

## 项目结构

```text
.
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 路由和依赖
│   │   ├── mqtt/         # paho-mqtt 后台订阅
│   │   ├── services/     # Python 业务逻辑
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app.py            # Streamlit 前端
│   ├── Dockerfile
│   └── requirements.txt
├── tools/
│   └── publish_sample.py # Python MQTT 设备模拟器
├── tests/
│   └── test_core.py
├── docker-compose.yml
└── README.md
```
