# 组 Webhook 协议接口文档

本文档用于消息转发服务接入水浸监测系统。转发服务负责接收设备 TCP/UDP/其它协议数据，解析后按本文约定转换为 JSON，并投递到水浸监测系统的组 Webhook 地址。

## 接入流程

1. 在后台创建 Webhook 组，并把组内传感器绑定到该组。
2. 每个组内传感器必须配置唯一 `device_imei`，用于转发服务上报时路由到具体传感器。
3. 转发服务保存该组的 Webhook URL，收到设备数据后向该 URL 发送 JSON。
4. 后端按 URL token 找到组，再按 payload 内的 IMEI 找到组内传感器，写入读数并触发告警/通知。

## Endpoint

```http
POST /api/sensors/group-webhook/{token}
Content-Type: application/json
```

示例：

```text
https://<your-domain>/api/sensors/group-webhook/<group_webhook_token>
```

说明：

- `{token}` 是组 Webhook token，等同于该入口的凭据，不能公开到日志、前端调试信息或第三方平台。
- 数据上报入口不需要后台登录 JWT；组管理和传感器管理接口仍需要后台登录权限。
- 生产环境建议通过 HTTPS 或内网专线访问。

## 通用 Payload

至少需要提供一个设备标识字段：`device_imei`、`imei`、`device_id` 三选一。后端按 `device_imei` -> `imei` -> `device_id` 的优先级取第一个非空值。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `device_imei` | string | 三选一 | 推荐字段，设备 IMEI，最长 32 字符 |
| `imei` | string | 三选一 | `device_imei` 的兼容别名 |
| `device_id` | string | 三选一 | `device_imei` 的兼容别名 |
| `timestamp` | string | 否 | ISO 8601 时间，例如 `2026-04-23T01:05:19Z`；不传则使用服务器当前时间 |
| `sensor_type` | string | 否 | `ultrasonic` 或 `immersion`，仅用于记录；实际解析以已绑定传感器类型为准 |
| `source` | string | 否 | 转发来源描述 |
| `source_ip` | string | 否 | 设备或转发端来源 IP |
| `source_port` | integer | 否 | 设备或转发端来源端口 |
| `msg_type` | integer | 否 | 原始协议消息类型 |
| `msg_type_name` | string | 否 | 原始协议消息类型名称 |
| `raw_hex` | string | 否 | 原始报文十六进制字符串，建议保留用于排障 |
| `packet_size` | integer | 否 | 原始报文长度 |
| `status` | string | 否 | `normal`、`warning`、`danger`、`alarm`、`offline`；超声波一般由后端阈值重新计算 |
| `voltage` | number | 否 | 设备电压，当前主要进入原始数据留存 |

当前组 Webhook 不需要转发 `battery_level`、`external_powered`、`signal_strength` 等字段。

## 浸水传感器 Payload

组内传感器类型为 `immersion` 时，必须提供以下字段之一：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `water_detected` | boolean | 推荐字段，`true` 表示检测到水，`false` 表示未检测到水 |
| `water_status` | integer | `0` 表示无水，非 `0` 表示有水 |
| `water_status_text` | string | `有水`、`浸水`、`wet`、`true`、`1` 会被识别为有水，其它值按无水处理 |

示例：

```json
{
  "device_imei": "000000000000001",
  "sensor_type": "immersion",
  "timestamp": "2026-04-23T01:05:19Z",
  "source_ip": "192.0.2.10",
  "source_port": 8080,
  "msg_type": 1,
  "msg_type_name": "状态变化",
  "water_status": 1,
  "water_status_text": "有水",
  "raw_hex": "010100"
}
```

浸水状态规则：

- 检测到水时，未显式传 `status` 会写入 `warning`。
- 未检测到水时，未显式传 `status` 会写入 `normal`。
- 如果显式传 `status`，后端会使用该状态。

## 超声波传感器 Payload

组内传感器类型为 `ultrasonic` 时，必须提供以下测量字段之一。后端按 `water_level` -> `measurement_value` -> `sensor_value` -> `adc_raw` 的顺序取第一个非空值。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `water_level` | number | 推荐字段，水位或测距值，单位按传感器配置约定为 cm |
| `measurement_value` | number | 测量值兼容字段，单位同 `water_level` |
| `sensor_value` | number | 测量值兼容字段，单位同 `water_level` |
| `adc_raw` | integer | 原始 ADC 值，仅建议在没有换算值时作为兜底 |

示例：

```json
{
  "device_imei": "000000000000002",
  "sensor_type": "ultrasonic",
  "timestamp": "2026-04-23T01:05:19Z",
  "source": "udp-forwarder",
  "msg_type": 1,
  "msg_type_name": "状态变化",
  "measurement_value": 12.8,
  "raw_hex": "55010c80",
  "packet_size": 4
}
```

超声波状态规则：

- 后端优先按传感器自身的 `warning_level`、`danger_level` 和 `threshold_condition` 计算状态。
- 当前设备如果上报的是“传感器到水面的测距值”，通常应把传感器配置为 `threshold_condition = less_or_equal`，即数值越小越危险。
- `status` 只作为缺少有效阈值配置时的兜底状态，不建议转发服务自行判定超声波告警等级。

## 成功响应

成功写入读数时返回 HTTP `201`：

```json
{
  "success": true,
  "message": "Group webhook data received successfully",
  "sensor_id": "sensor-001",
  "device_imei": "000000000000001",
  "reading_id": 123
}
```

## 常见错误

| HTTP 状态 | detail | 含义 |
| --- | --- | --- |
| `400` | `Sensor is inactive` | 目标传感器已停用 |
| `404` | `Webhook group not found` | token 不存在或组已停用 |
| `404` | `No sensor binding found for this IMEI in the webhook group` | IMEI 未绑定到该组内传感器 |
| `422` | `Group webhook data requires device IMEI` | 缺少 `device_imei` / `imei` / `device_id` |
| `422` | `Immersion group webhook data requires water status` | 浸水传感器缺少水浸状态字段 |
| `422` | `Ultrasonic group webhook data requires water_level or another measurement field` | 超声波传感器缺少测量值 |

## curl 示例

浸水：

```bash
curl -X POST "https://<your-domain>/api/sensors/group-webhook/<group_webhook_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "device_imei": "000000000000001",
    "timestamp": "2026-04-23T01:05:19Z",
    "water_detected": true,
    "raw_hex": "010100"
  }'
```

超声波：

```bash
curl -X POST "https://<your-domain>/api/sensors/group-webhook/<group_webhook_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "device_imei": "000000000000002",
    "timestamp": "2026-04-23T01:05:19Z",
    "measurement_value": 12.8,
    "raw_hex": "55010c80"
  }'
```

## 转发服务建议

- 请求超时建议设置为 5-10 秒。
- `2xx` 视为成功；非 `2xx` 需要记录响应 body。
- `400`、`404`、`422` 通常是配置或 payload 问题，不建议无限重试。
- 网络超时或 `5xx` 可重试，但当前接口没有幂等键，超时后重试可能产生重复读数。
- 建议总是传 `timestamp`，优先使用 UTC ISO 8601 格式并带 `Z`。
- 建议保留 `raw_hex`、`source_ip`、`source_port`，便于后续排查设备报文。
- 转发服务不应自动创建传感器；传感器和 IMEI 绑定应在后台完成。
