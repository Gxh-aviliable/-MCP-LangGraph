"""
API 测试脚本 - 用于测试后端 API
"""
import asyncio
import json
import requests
from typing import Dict, Any

# API 基础 URL
BASE_URL = "http://localhost:8000"

# ===================== 同步 API 测试 =====================

def test_health_check():
    """测试健康检查接口"""
    print("\n" + "="*50)
    print("测试: 健康检查")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False

def test_get_cities():
    """测试获取城市列表"""
    print("\n" + "="*50)
    print("测试: 获取热门城市")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/api/cities")
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(f"城市数量: {len(data.get('data', []))}")
        print(f"示例: {json.dumps(data['data'][:2], indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False

def test_get_interests():
    """测试获取兴趣分类"""
    print("\n" + "="*50)
    print("测试: 获取兴趣分类")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/api/interests")
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(f"分类数量: {len(data.get('data', []))}")
        print(f"示例: {json.dumps(data['data'][:2], indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False

def test_get_accommodation_types():
    """测试获取住宿类型"""
    print("\n" + "="*50)
    print("测试: 获取住宿类型")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/api/accommodation-types")
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(f"住宿类型数量: {len(data.get('data', []))}")
        print(f"示例: {json.dumps(data['data'][:3], indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False

def test_plan_trip():
    """测试生成旅行计划"""
    print("\n" + "="*50)
    print("测试: 生成旅行计划")
    print("="*50)
    
    # 请求数据
    payload = {
        "city": "北京",
        "start_date": "2026-01-30",
        "end_date": "2026-02-02",
        "interests": ["故宫", "国家博物馆"],
        "accommodation_type": "五星级",
        "budget_per_day": 1500,
        "transportation_mode": "地铁+出租车"
    }
    
    print(f"请求数据: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print("\n正在生成行程计划，请稍候...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/plan",
            json=payload,
            timeout=300  # 5分钟超时
        )
        print(f"状态码: {response.status_code}")
        
        data = response.json()
        
        if data['success']:
            print("\n✅ 行程计划生成成功!")
            trip_plan = data['data']
            print(f"\n行程概览:")
            print(f"  城市: {trip_plan['city']}")
            print(f"  日期: {trip_plan['start_date']} 至 {trip_plan['end_date']}")
            print(f"  天数: {len(trip_plan['days'])} 天")
            
            if trip_plan.get('budget'):
                budget = trip_plan['budget']
                print(f"\n预算总额:")
                print(f"  景点: ¥{budget.get('total_attractions', 0)}")
                print(f"  酒店: ¥{budget.get('total_hotels', 0)}")
                print(f"  餐饮: ¥{budget.get('total_meals', 0)}")
                print(f"  交通: ¥{budget.get('total_transportation', 0)}")
                print(f"  总计: ¥{budget.get('total', 0)}")
            
            print(f"\n第一天行程:")
            first_day = trip_plan['days'][0]
            print(f"  日期: {first_day['date']}")
            print(f"  景点数: {len(first_day.get('attractions', []))}")
            if first_day.get('attractions'):
                print(f"  首个景点: {first_day['attractions'][0]['name']}")
            
            # 保存完整响应
            with open('trip_plan_response.json', 'w', encoding='utf-8') as f:
                json.dump(trip_plan, f, indent=2, ensure_ascii=False)
            print("\n✅ 完整响应已保存到 trip_plan_response.json")
            
            return True
        else:
            print(f"\n❌ 规划失败: {data['message']}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时 (超过 5 分钟)")
        return False
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False

# ===================== WebSocket 测试 =====================

async def test_websocket_plan():
    """使用 WebSocket 测试规划"""
    print("\n" + "="*50)
    print("测试: WebSocket 实时规划")
    print("="*50)
    
    import websockets
    
    ws_url = f"ws://localhost:8000/ws/plan"
    
    payload = {
        "city": "上海",
        "start_date": "2026-02-01",
        "end_date": "2026-02-03",
        "interests": ["外滩", "豫园"],
        "accommodation_type": "四星级",
        "budget_per_day": 1200,
        "transportation_mode": "地铁"
    }
    
    print(f"连接到: {ws_url}")
    print(f"请求数据: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print("\n等待服务器响应...")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            # 发送请求
            await websocket.send(json.dumps({
                "action": "plan",
                "data": payload
            }))
            
            # 接收响应
            while True:
                try:
                    message_text = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=300  # 5分钟超时
                    )
                    message = json.loads(message_text)
                    
                    msg_type = message.get('type', 'unknown')
                    msg_content = message.get('message', '')
                    
                    print(f"\n[{msg_type.upper()}] {msg_content}")
                    
                    if msg_type == 'success':
                        print("\n✅ WebSocket 规划成功!")
                        return True
                    elif msg_type == 'error':
                        print("\n❌ WebSocket 规划失败!")
                        return False
                    
                except asyncio.TimeoutError:
                    print("\n⏱️ 操作超时")
                    return False
                    
    except Exception as e:
        print(f"❌ WebSocket 错误: {str(e)}")
        return False

# ===================== 主函数 =====================

def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("╔════════════════════════════════════════╗")
    print("║   AI 旅行规划助手 - API 测试套件       ║")
    print("╚════════════════════════════════════════╝")
    
    # 检查服务是否在线
    print("\n检查服务是否在线...")
    if not test_health_check():
        print("\n❌ 服务不在线，请先启动后端服务")
        return
    
    print("\n✅ 服务在线，开始测试")
    
    # 运行测试
    results = {
        "健康检查": test_health_check(),
        "获取城市": test_get_cities(),
        "获取兴趣": test_get_interests(),
        "获取住宿": test_get_accommodation_types(),
        "生成计划": test_plan_trip(),
    }
    
    # 测试摘要
    print("\n" + "="*50)
    print("测试摘要")
    print("="*50)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    # 统计
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")
    
    # WebSocket 测试（可选）
    print("\n" + "="*50)
    print("是否测试 WebSocket？(需要 websockets 库)")
    print("="*50)
    try:
        import websockets
        print("✅ websockets 库已安装")
        
        user_input = input("\n是否运行 WebSocket 测试? (y/n): ").lower()
        if user_input == 'y':
            ws_result = asyncio.run(test_websocket_plan())
            print(f"\nWebSocket 测试: {'✅ 通过' if ws_result else '❌ 失败'}")
    except ImportError:
        print("⚠️ websockets 库未安装，跳过 WebSocket 测试")
        print("安装: pip install websockets")

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⏹️ 测试已中止")
    except Exception as e:
        print(f"\n❌ 测试出错: {str(e)}")
        import traceback
        traceback.print_exc()
