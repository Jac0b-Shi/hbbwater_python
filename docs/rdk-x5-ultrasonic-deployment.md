# RDK X5 超声传感器 MQTT 部署复刻手册

本文档用于在新的 RDK X5 上复刻超声波液位采集链路。部署目标是让 RDK X5 通过 `/dev/ttyS2` 读取 L07A 类 UART 超声传感器，并把数据发布到本项目自带的 EMQX MQTT Broker。

当前方案只使用局域网或 Tailscale/Headscale 访问本机 MQTT Broker，暂不使用 BC260 NB-IoT。

## 部署拓扑

```text
L07A 超声传感器
  |
  | UART 115200, /dev/ttyS2
  v
RDK X5
  |
  | MQTT over LAN or Tailscale
  v
Windows 本机 hbbwater_python
  |
  | docker compose
  v
EMQX (:1883) -> FastAPI backend (:8000) -> PostgreSQL -> Streamlit (:8501)
```

默认 Topic：

```text
hbbwater/ultrasonic/{device_id}/data
```

核心约定：

- RDK X5 只负责采集和发布 MQTT。
- 本机 `hbbwater_python` 负责运行 EMQX、PostgreSQL、FastAPI 和 Streamlit。
- L07A 上报值表示“探头到液面的距离”，距离越小越危险。
- 后端会把 MQTT 中的 `unit=mm` 自动换算为 `cm`。
- 这类超声距离型设备的后端阈值方向应设置为 `less_or_equal`。

## 1. 本机启动 hbbwater_python

在 Windows 本机 PowerShell 执行：（项目地址自行更改为你项目实际在的地址）

```powershell
cd D:\CodeProjects\hbbwater_python
docker compose up -d
docker compose ps
```

确认服务状态中至少包含：

| 服务 | 端口 | 说明 |
|------|------|------|
| `hbbwater-python-emqx` | `1883`, `18083` | MQTT Broker 与 EMQX 控制台 |
| `hbbwater-python-backend` | `8000` | FastAPI 后端和 MQTT 消费线程 |
| `hbbwater-python-frontend` | `8501` | Streamlit 运维控制台 |
| `hbbwater-python-postgres` | Docker 内网 | 数据库 |

如果通过 Tailscale/Headscale 接入，记录本机 Tailscale IPv4：

```powershell
tailscale ip -4
```

示例：

```text
100.64.0.11
```

后文用 `<broker-ip>` 表示这个地址。局域网稳定时也可以直接使用 Windows 本机局域网 IP。

## 2. RDK X5 基础检查

通过局域网、USB RNDIS 或 Tailscale 登录 RDK X5：

```bash
ssh root@<rdk-ip>
```

检查系统、网络、串口和 Python 依赖：

```bash
hostname
uname -a
ip -brief addr
ip route
ls -l /dev/ttyS2
python3 --version
python3 -c "import serial, paho.mqtt.client; print('python deps ok')"
```

如果缺少 Python 依赖：

```bash
apt update
apt install -y python3-pip
pip3 install pyserial paho-mqtt
```

RDK X5 上应能看到 `/dev/ttyS2`。如果不存在，需要先确认 UART2 device tree overlay 是否已经启用，并重启 RDK。

## 3. 接入 Headscale/Tailscale

如果设备经常换局域网，建议先接入 Headscale/Tailscale。`--login-server` 用于自定义 headscale 服务器 URL 。

```bash
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled

tailscale up \
  --login-server=https://headscale.example.com/ \
  --authkey=<headscale-authkey> \
  --accept-dns=false \
  --accept-routes=false

tailscale ip -4
tailscale status --peers=false
```

不要把真实 authkey 写进仓库、文档提交或日志截图。复刻新设备时使用 Headscale 后台新生成的短期 authkey。

本机验证 RDK 可达：

```powershell
tailscale ping <rdk-tailscale-ip>
```

RDK 验证本机 MQTT/API/前端端口可达：

```bash
python3 - <<'PY'
import socket

for host, port in [("<broker-ip>", 1883), ("<broker-ip>", 8000), ("<broker-ip>", 8501)]:
    sock = socket.socket()
    sock.settimeout(5)
    try:
        sock.connect((host, port))
        print(f"OK {host}:{port}")
    except Exception as exc:
        print(f"FAIL {host}:{port} {exc}")
    finally:
        sock.close()
PY
```

## 4. 部署超声 MQTT 脚本

本项目提供 RDK 侧采集脚本：

```text
tools/ultrasonic_mqtt.py
```

从 Windows 本机复制到 RDK：

```powershell
ssh root@<rdk-ip> "mkdir -p /root/src/hbbwater_python/tools"
scp D:\CodeProjects\hbbwater_python\tools\ultrasonic_mqtt.py root@<rdk-ip>:/root/src/hbbwater_python/tools/
```

RDK 上检查脚本：

```bash
chmod +x /root/src/hbbwater_python/tools/ultrasonic_mqtt.py
python3 -m py_compile /root/src/hbbwater_python/tools/ultrasonic_mqtt.py
python3 /root/src/hbbwater_python/tools/ultrasonic_mqtt.py --help
```

脚本使用的 L07A 协议：

```text
[0xFF, Data_H, Data_L, SUM]
SUM = (0xFF + Data_H + Data_L) & 0xFF
```

特殊值处理：

| 原始值 | 含义 | 行为 |
|--------|------|------|
| `0xFFFD` | 未检测到物体 | 作为无效样本跳过 |
| `0xFFFE` | 同频干扰 | 作为无效样本跳过 |
| 超过 `--max-distance-mm` | 超出有效距离 | 作为无效样本跳过 |

脚本会在一个采样窗口内收集多个有效样本，按 `--trim-ratio` 去掉两端极值后取修剪均值，再发布 MQTT。

## 5. 手动采集发布测试

为每台 RDK 规划唯一设备 ID，例如：

```text
rdk-x5-ultrasonic-01
rdk-x5-ultrasonic-02
rdk-x5-ultrasonic-lab-a
```

先手动发布一条数据：

```bash
python3 /root/src/hbbwater_python/tools/ultrasonic_mqtt.py \
  --port /dev/ttyS2 \
  --broker <broker-ip> \
  --device-id rdk-x5-ultrasonic-01 \
  --threshold-mm 200 \
  --count 1 \
  --interval 8 \
  --window-size 3 \
  --sample-interval 0.2 \
  --verbose
```

正常输出示例：

```text
publishing /dev/ttyS2 -> mqtt://<broker-ip>:1883/hbbwater/ultrasonic/rdk-x5-ultrasonic-01/data device_id=rdk-x5-ultrasonic-01
sample 476mm (1/3)
sample 476mm (2/3)
sample 476mm (3/3)
published #1: 476mm samples=3
```

如果偶尔出现以下输出，不一定是故障：

```text
read error: no object detected
```

这表示传感器返回了合法帧 `0xFFFD`，语义是当前未检测到物体。只要后续有有效样本并成功 publish，就可以继续使用。

## 6. 配置后端传感器阈值

首次 MQTT 上报后，后端会自动注册传感器。由于 L07A 上报的是距离值，越小越危险，需要把该设备的阈值方向改成 `less_or_equal`。

在 Windows 本机执行：

```powershell
docker exec hbbwater-python-postgres psql -U hbbwater -d hbbwater -c "UPDATE sensors SET name='RDK X5 Ultrasonic 01', location='RDK X5 / ttyS2', threshold_warn=30, threshold_danger=20, threshold_dir='less_or_equal' WHERE device_id='rdk-x5-ultrasonic-01';"
```

推荐初始阈值：

| 字段 | 单位 | 建议值 | 含义 |
|------|------|--------|------|
| `threshold_warn` | cm | `30` | 距离小于等于 30 cm 时预警 |
| `threshold_danger` | cm | `20` | 距离小于等于 20 cm 时危险 |
| `threshold_dir` | - | `less_or_equal` | 数值越小越危险 |
| `--threshold-mm` | mm | `200` | 脚本 raw payload 中的现场判断阈值 |

注意：`--threshold-mm` 只写入 MQTT 原始 payload 中的 `high_water` 和 `threshold_mm` 字段；后端告警以数据库里的 `threshold_warn`、`threshold_danger`、`threshold_dir` 为准。

## 7. 创建 systemd 常驻服务

在 RDK 上创建服务文件：

```bash
cat > /etc/systemd/system/hbbwater-ultrasonic-mqtt.service <<'EOF'
[Unit]
Description=HBBWater RDK X5 ultrasonic MQTT publisher
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 /root/src/hbbwater_python/tools/ultrasonic_mqtt.py --port /dev/ttyS2 --broker <broker-ip> --device-id rdk-x5-ultrasonic-01 --threshold-mm 200 --interval 5 --window-size 8 --sample-interval 0.1 --max-distance-mm 3000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

启动并设置开机自启：

```bash
systemctl daemon-reload
systemctl enable --now hbbwater-ultrasonic-mqtt.service
```

查看状态和实时日志：

```bash
systemctl status hbbwater-ultrasonic-mqtt.service --no-pager
journalctl -u hbbwater-ultrasonic-mqtt.service -f
```

正常日志示例：

```text
publishing /dev/ttyS2 -> mqtt://<broker-ip>:1883/hbbwater/ultrasonic/rdk-x5-ultrasonic-01/data device_id=rdk-x5-ultrasonic-01
published #1: 473mm samples=8
published #2: 474mm samples=8
```

## 8. 验证数据库入库

在 Windows 本机查询最新读数：

```powershell
docker exec hbbwater-python-postgres psql -U hbbwater -d hbbwater -t -A -F "|" -c "SELECT s.device_id, s.last_value, s.last_unit, s.threshold_warn, s.threshold_danger, s.threshold_dir, r.status, r.raw_json->>'sample_count', r.raw_json->>'high_water', r.created_at FROM sensors s JOIN sensor_readings r ON r.sensor_id = s.id WHERE s.device_id = 'rdk-x5-ultrasonic-01' ORDER BY r.created_at DESC LIMIT 1;"
```

正常结果示例：

```text
rdk-x5-ultrasonic-01|47.5|cm|30|20|less_or_equal|normal|8|false|2026-05-12 15:31:02.157554+00
```

也可以查询最近 10 条读数：

```powershell
docker exec hbbwater-python-postgres psql -U hbbwater -d hbbwater -c "SELECT r.created_at, r.value, r.unit, r.status, r.raw_json->>'raw_min_mm' AS raw_min_mm, r.raw_json->>'raw_max_mm' AS raw_max_mm FROM sensor_readings r JOIN sensors s ON s.id = r.sensor_id WHERE s.device_id = 'rdk-x5-ultrasonic-01' ORDER BY r.created_at DESC LIMIT 10;"
```

## 9. 多台 RDK 复刻参数表

每台 RDK 至少需要唯一化以下参数：

| 参数 | 示例 | 说明 |
|------|------|------|
| `--device-id` | `rdk-x5-ultrasonic-01` | 后端唯一设备编号，不能重复 |
| `name` | `RDK X5 Ultrasonic 01` | 控制台显示名称 |
| `location` | `实验室 A / ttyS2` | 控制台点位说明 |
| `--broker` | `100.64.0.7` | 本机 MQTT Broker 地址 |
| `threshold_warn` | `30` | 后端预警阈值，单位 cm |
| `threshold_danger` | `20` | 后端危险阈值，单位 cm |
| `--threshold-mm` | `200` | 脚本 payload 阈值，单位 mm |

建议设备 ID 命名规则：

```text
rdk-x5-ultrasonic-<位置或序号>
```

例如：

```text
rdk-x5-ultrasonic-lab-a
rdk-x5-ultrasonic-basement-01
rdk-x5-ultrasonic-pump-room
```

## 10. 故障排查

### RDK 无法访问 Broker

检查 RDK 到本机端口：

```bash
python3 - <<'PY'
import socket
sock = socket.socket()
sock.settimeout(5)
sock.connect(("<broker-ip>", 1883))
print("mqtt port ok")
sock.close()
PY
```

如果失败：

- 确认本机 `docker compose ps` 中 EMQX 正常运行。
- 确认本机防火墙允许 Tailscale 或局域网访问 `1883`。
- 确认 `<broker-ip>` 使用的是本机 Tailscale IP 或正确局域网 IP。
- 确认 RDK `tailscale status` 在线。

### 服务反复重启

查看日志：

```bash
journalctl -u hbbwater-ultrasonic-mqtt.service -n 100 --no-pager
```

常见原因：

- `/dev/ttyS2` 不存在或未启用。
- `pyserial` 或 `paho-mqtt` 未安装。
- Broker 地址不可达。
- 传感器持续返回无效帧，超过脚本连续错误上限。

### 读数入库但状态误报

检查阈值方向：

```powershell
docker exec hbbwater-python-postgres psql -U hbbwater -d hbbwater -c "SELECT device_id, last_value, last_unit, threshold_warn, threshold_danger, threshold_dir FROM sensors WHERE device_id='rdk-x5-ultrasonic-01';"
```

L07A 距离型设备应为：

```text
threshold_dir = less_or_equal
```

如果仍是 `greater_or_equal`，会把距离较大的正常状态误判为危险。

### Tailscale 有 IPv6 iptables 健康告警

某些 RDK 内核可能不支持完整 IPv6 netfilter，`tailscale status` 可能出现类似 `ip6tables` 的 health check 告警。只要以下条件成立，一般不影响本方案：

- `tailscale ip -4` 能拿到 IPv4。
- 本机 `tailscale ping <rdk-tailscale-ip>` 成功。
- RDK 能连接 `<broker-ip>:1883`。

本方案不依赖 Tailscale 子网路由，也不要求 `--accept-routes=true`。

## 11. 维护命令速查

RDK 查看 Tailscale IP：

```bash
tailscale ip -4
```

RDK 重启采集服务：

```bash
systemctl restart hbbwater-ultrasonic-mqtt.service
```

RDK 禁用采集服务：

```bash
systemctl disable --now hbbwater-ultrasonic-mqtt.service
```

RDK 临时手动发布一条：

```bash
python3 /root/src/hbbwater_python/tools/ultrasonic_mqtt.py \
  --port /dev/ttyS2 \
  --broker <broker-ip> \
  --device-id rdk-x5-ultrasonic-01 \
  --threshold-mm 200 \
  --count 1 \
  --verbose
```

本机查看容器：

```powershell
cd D:\CodeProjects\hbbwater_python
docker compose ps
```

本机查看后端 MQTT 消费日志：

```powershell
docker compose logs -f backend
```

本机查看最新数据库读数：

```powershell
docker exec hbbwater-python-postgres psql -U hbbwater -d hbbwater -c "SELECT s.device_id, s.last_value, s.last_unit, s.threshold_dir, r.status, r.created_at FROM sensors s JOIN sensor_readings r ON r.sensor_id=s.id ORDER BY r.created_at DESC LIMIT 10;"
```

