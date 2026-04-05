#!/usr/bin/env python3
"""检查传感器数据是否已存储"""
import requests
import sys

def check_sensor_data(sensor_id="1", limit=10):
    url = f"http://localhost/api/sensors/{sensor_id}/readings?limit={limit}"
    
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        print(f"传感器 {sensor_id} 数据查询结果:")
        print(f"总记录数: {data['total']}")
        print(f"当前页: {data['page']}")
        print(f"每页大小: {data['page_size']}")
        print()
        
        print("最近读数:")
        print("-" * 60)
        for i, item in enumerate(data['items'][:5]):
            time = item['recorded_at'][:19].replace('T', ' ')
            status = item['status']
            water = "是" if item['water_detected'] else "否"
            duration = f"{item['duration']}秒" if item['duration'] else "-"
            battery = f"{item['battery_level']}%" if item['battery_level'] else "-"
            print(f"{i+1}. {time} | 状态:{status:8} | 浸水:{water} | 持续:{duration:8} | 电量:{battery}")
        
        if data['total'] > 0:
            print()
            print("✅ 数据验证成功！传感器正在正常接收和存储数据。")
        else:
            print("⚠️ 暂无数据记录")
            
    except Exception as e:
        print(f"查询失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_sensor_data()
