"""测试脚本 - 运行后端并测试 agent 行为"""
import asyncio
import sys
import io
import os

# Windows 控制台 UTF-8 支持
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent import TripChatSession
from backend.model import TripRequest


async def test_agent():
    """测试 agent 行为"""
    print("=" * 60)
    print("测试 Agent 工具调用能力")
    print("=" * 60)

    # 创建测试请求
    request = TripRequest(
        city="北京",
        start_date="2026-03-27",
        end_date="2026-03-28",
        interests=["历史古迹", "博物馆"],
        accommodation_type="中档",
        budget_per_day=500,
        transportation_mode="地铁"
    )

    print(f"\n[测试请求]")
    print(f"  城市: {request.city}")
    print(f"  日期: {request.start_date} - {request.end_date}")
    print(f"  兴趣: {request.interests}")
    print()

    # 创建会话并执行
    session = TripChatSession()
    await session.initialize()

    print("\n[开始执行 Agent 流程...]\n")

    # 执行规划
    plan = await session.start(request)

    print("\n" + "=" * 60)
    print("执行结果:")
    print("=" * 60)

    if plan:
        print(session.format_plan(plan))
    else:
        print("[FAIL] 规划失败")


if __name__ == "__main__":
    asyncio.run(test_agent())