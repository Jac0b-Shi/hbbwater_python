#!/usr/bin/env python3
"""
传感器测试数据发送脚本
用于向浸水传感器发送模拟数据，验证最近读数、历史趋势等功能

使用方法:
    python send_test_data.py --sensor 1 --token 8b69faff1697440f
    
    # 发送历史数据（过去24小时，每5分钟一条）
    python send_test_data.py --sensor 1 --token 8b69faff1697440f --history --hours 24 --interval 300
"""

import argparse
import json
import random
import time
from datetime import datetime, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    print("错误: 需要安装 requests 库")
    print("运行: pip install requests")
    exit(1)


class SensorTestClient:
    """传感器测试数据发送客户端"""
    
    def __init__(self, base_url: str = "http://localhost"):
        self.base_url = base_url.rstrip('/')
        
    def send_immersion_reading(
        self,
        token: str,
        water_detected: bool = False,
        duration: int = 0,
        severity: str = "low",
        status: str = "normal",
        timestamp: Optional[datetime] = None,
        battery_level: Optional[float] = None,
        signal_strength: Optional[int] = None
    ) -> dict:
        """
        发送浸水传感器读数
        
        Args:
            token: Webhook token
            water_detected: 是否检测到水
            duration: 浸水持续时间(秒)
            severity: 严重程度 (low/medium/high)
            status: 状态 (normal/warning/danger/alarm/offline)
            timestamp: 时间戳，默认为当前时间
            battery_level: 电池电量(0-100)
            signal_strength: 信号强度(dBm)
        """
        url = f"{self.base_url}/api/sensors/webhook/{token}"
        
        data = {
            "water_detected": water_detected,
            "duration": duration,
            "severity": severity,
            "status": status
        }
        
        if timestamp:
            data["timestamp"] = timestamp.isoformat()
        if battery_level is not None:
            data["battery_level"] = battery_level
        if signal_strength is not None:
            data["signal_strength"] = signal_strength
            
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"发送失败: {e}")
            return {"error": str(e)}
    
    def generate_random_reading(self) -> dict:
        """生成随机浸水传感器读数"""
        # 随机状态：70%正常，20%预警，10%危险
        rand = random.random()
        if rand < 0.7:
            status = "normal"
            water_detected = False
            duration = 0
            severity = "low"
        elif rand < 0.9:
            status = "warning"
            water_detected = True
            duration = random.randint(10, 300)
            severity = random.choice(["low", "medium"])
        else:
            status = "danger"
            water_detected = True
            duration = random.randint(300, 3600)
            severity = random.choice(["medium", "high"])
        
        return {
            "water_detected": water_detected,
            "duration": duration,
            "severity": severity,
            "status": status,
            "battery_level": round(random.uniform(60, 100), 1),
            "signal_strength": random.randint(-85, -50)
        }
    
    def send_history_data(
        self,
        token: str,
        hours: int = 24,
        interval_seconds: int = 300,
        randomize: bool = True
    ) -> list:
        """
        发送历史数据
        
        Args:
            token: Webhook token
            hours: 历史数据时间跨度(小时)
            interval_seconds: 数据间隔(秒)
            randomize: 是否随机生成数据
        """
        results = []
        now = datetime.utcnow()
        total_records = int(hours * 3600 / interval_seconds)
        
        print(f"准备发送 {total_records} 条历史数据，时间跨度 {hours} 小时...")
        
        for i in range(total_records):
            timestamp = now - timedelta(seconds=(total_records - i) * interval_seconds)
            
            if randomize:
                reading = self.generate_random_reading()
            else:
                reading = {
                    "water_detected": False,
                    "duration": 0,
                    "severity": "low",
                    "status": "normal",
                    "battery_level": 85.0,
                    "signal_strength": -70
                }
            
            result = self.send_immersion_reading(token=token, timestamp=timestamp, **reading)
            results.append(result)
            
            if (i + 1) % 10 == 0:
                print(f"  已发送 {i + 1}/{total_records} 条数据...")
            
            # 避免请求过快
            time.sleep(0.05)
        
        print(f"完成！共发送 {len(results)} 条数据")
        return results
    
    def send_test_scenario(self, token: str, scenario: str = "normal"):
        """
        发送特定测试场景的数据序列
        
        Args:
            token: Webhook token
            scenario: 场景名称 (normal/leak/flood)
        """
        scenarios = {
            "normal": [
                {"status": "normal", "water_detected": False, "duration": 0, "severity": "low"},
                {"status": "normal", "water_detected": False, "duration": 0, "severity": "low"},
                {"status": "normal", "water_detected": False, "duration": 0, "severity": "low"},
            ],
            "leak": [
                {"status": "normal", "water_detected": False, "duration": 0, "severity": "low"},
                {"status": "warning", "water_detected": True, "duration": 60, "severity": "low"},
                {"status": "warning", "water_detected": True, "duration": 180, "severity": "medium"},
                {"status": "normal", "water_detected": False, "duration": 0, "severity": "low"},
            ],
            "flood": [
                {"status": "normal", "water_detected": False, "duration": 0, "severity": "low"},
                {"status": "warning", "water_detected": True, "duration": 120, "severity": "medium"},
                {"status": "danger", "water_detected": True, "duration": 600, "severity": "high"},
                {"status": "danger", "water_detected": True, "duration": 1800, "severity": "high"},
                {"status": "warning", "water_detected": True, "duration": 2400, "severity": "medium"},
            ]
        }
        
        if scenario not in scenarios:
            print(f"未知场景: {scenario}")
            return
        
        print(f"发送 '{scenario}' 场景测试数据...")
        now = datetime.utcnow()
        
        for i, data in enumerate(scenarios[scenario]):
            timestamp = now - timedelta(minutes=len(scenarios[scenario]) - i)
            result = self.send_immersion_reading(
                token=token,
                timestamp=timestamp,
                battery_level=round(random.uniform(70, 95), 1),
                signal_strength=random.randint(-80, -60),
                **data
            )
            print(f"  数据 {i+1}: {data['status']} - {'有浸水' if data['water_detected'] else '正常'}")
            time.sleep(0.1)
        
        print("场景数据发送完成!")


def main():
    parser = argparse.ArgumentParser(
        description="向传感器发送测试数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 发送单条正常数据
  python send_test_data.py --token 8b69faff1697440f
  
  # 发送浸水告警数据
  python send_test_data.py --token 8b69faff1697440f --detected --duration 300 --severity high --status danger
  
  # 发送24小时历史数据
  python send_test_data.py --token 8b69faff1697440f --history --hours 24
  
  # 发送测试场景（正常/漏水/浸水）
  python send_test_data.py --token 8b69faff1697440f --scenario flood
        """
    )
    
    parser.add_argument("--token", required=True, help="Webhook token")
    parser.add_argument("--url", default="http://localhost", help="API基础URL (默认: http://localhost)")
    
    # 单条数据参数
    parser.add_argument("--detected", action="store_true", help="是否检测到水")
    parser.add_argument("--duration", type=int, default=0, help="浸水持续时间(秒)")
    parser.add_argument("--severity", choices=["low", "medium", "high"], default="low", help="严重程度")
    parser.add_argument("--status", choices=["normal", "warning", "danger", "alarm", "offline"], 
                       default="normal", help="状态")
    parser.add_argument("--battery", type=float, help="电池电量")
    parser.add_argument("--signal", type=int, help="信号强度")
    
    # 批量/场景参数
    parser.add_argument("--history", action="store_true", help="发送历史数据")
    parser.add_argument("--hours", type=int, default=24, help="历史数据时间跨度(小时)")
    parser.add_argument("--interval", type=int, default=300, help="数据间隔(秒)")
    parser.add_argument("--scenario", choices=["normal", "leak", "flood"], help="测试场景")
    
    args = parser.parse_args()
    
    client = SensorTestClient(args.url)
    
    if args.scenario:
        # 发送场景数据
        client.send_test_scenario(args.token, args.scenario)
    elif args.history:
        # 发送历史数据
        client.send_history_data(args.token, args.hours, args.interval)
    else:
        # 发送单条数据
        result = client.send_immersion_reading(
            token=args.token,
            water_detected=args.detected,
            duration=args.duration,
            severity=args.severity,
            status=args.status,
            battery_level=args.battery,
            signal_strength=args.signal
        )
        print(f"发送结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if "error" not in result:
            print("\n✅ 数据发送成功!")
            print(f"   状态: {args.status}")
            print(f"   浸水检测: {'是' if args.detected else '否'}")
            if args.detected:
                print(f"   持续时间: {args.duration}秒")
                print(f"   严重程度: {args.severity}")


if __name__ == "__main__":
    main()
