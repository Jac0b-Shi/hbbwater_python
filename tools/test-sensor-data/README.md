# 传感器测试数据发送工具

用于向浸水传感器发送模拟数据，验证最近读数、历史趋势等功能。

## 前提条件

```bash
pip install requests
```

## 快速开始

### 1. 发送单条测试数据

```bash
# 发送正常状态数据
python send_test_data.py --token 8b69faff1697440f

# 发送浸水告警数据
python send_test_data.py --token 8b69faff1697440f --detected --duration 300 --severity high --status danger
```

### 2. 发送测试场景

```bash
# 正常场景（连续正常读数）
python send_test_data.py --token 8b69faff1697440f --scenario normal

# 漏水场景（从正常到预警再到恢复）
python send_test_data.py --token 8b69faff1697440f --scenario leak

# 浸水场景（从正常到危险级别）
python send_test_data.py --token 8b69faff1697440f --scenario flood
```

### 3. 发送历史数据（用于验证趋势图）

```bash
# 发送24小时历史数据，每5分钟一条（共288条）
python send_test_data.py --token 8b69faff1697440f --history --hours 24

# 发送12小时历史数据，每10分钟一条
python send_test_data.py --token 8b69faff1697440f --history --hours 12 --interval 600
```

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--token` | Webhook Token（必填） | `8b69faff1697440f` |
| `--url` | API基础地址 | `http://localhost` |
| `--detected` | 是否检测到水 | 无值，存在即为True |
| `--duration` | 浸水持续时间(秒) | `300` |
| `--severity` | 严重程度 | `low`/`medium`/`high` |
| `--status` | 状态 | `normal`/`warning`/`danger` |
| `--battery` | 电池电量 | `85.5` |
| `--signal` | 信号强度 | `-70` |
| `--history` | 发送历史数据模式 | 无值，存在即启用 |
| `--hours` | 历史数据时间跨度 | `24` |
| `--interval` | 数据间隔(秒) | `300` |
| `--scenario` | 测试场景 | `normal`/`leak`/`flood` |

## 验证步骤

1. **发送测试数据**
   ```bash
   python send_test_data.py --token 8b69faff1697440f --scenario flood
   ```

2. **查看最近读数**
   - 打开浏览器访问 http://localhost
   - 进入"传感器管理"页面
   - 点击传感器"详情"按钮
   - 查看"最近读数"表格

3. **查看历史趋势**
   - 在传感器详情页查看"历史趋势"图表
   - 或使用"历史数据"页面查看时间范围数据

## 常见问题

**Q: 如何获取传感器的 webhook token？**
A: 在传感器管理页面编辑传感器，选择 Webhook 上报方式，复制的地址中包含 token。

**Q: 发送历史数据后看不到图表？**
A: 历史数据按时间戳排序，请确保：
1. 数据时间范围在图表选择的时间范围内
2. 刷新页面或重新选择时间范围

**Q: 可以发送超声波传感器数据吗？**
A: 当前脚本针对浸水传感器，如需超声波传感器支持，可修改数据字段为：
```python
{
    "water_level": 25.5,
    "battery_level": 85,
    "signal_strength": -70,
    "status": "normal"
}
```
