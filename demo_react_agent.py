"""ReAct Agent 使用演示

展示真正的 Agent 智能推理：
- Reasoning：思考下一步该做什么
- Acting：执行行动
- Observation：观察结果
- Reflection：反思质量，决定是否继续

运行方式:
    python demo_react_agent.py
"""
import asyncio
import os
import sys

# 设置使用 ReAct Agent
os.environ['USE_REACT_AGENT'] = 'true'

from backend.agent import ReActChatSession
from backend.config.settings import settings


async def demo_react_agent():
    """演示 ReAct Agent 的使用"""
    print("=" * 60)
    print("🤖 ReAct Agent 演示")
    print("=" * 60)
    print("""
这个 Agent 会展示真正的智能推理：
1. 每一步都会【思考】下一步该做什么
2. 执行【行动】后观察结果
3. 【反思】结果质量，决定是否继续
4. 循环直到满意或达到最大迭代次数

这是与固定流水线的核心区别！
""")

    # 创建 ReAct Agent 会话
    print("[初始化] 创建 ReAct Agent 会话...")
    session = ReActChatSession()
    await session.initialize()
    print("[初始化] 完成！\n")

    # 模拟用户请求
    test_requests = [
        "我想从上海去北京玩三天，喜欢历史古迹",
        # "我不看景点，只想去吃美食",  # 测试跳过景点
        # "我已经订好酒店了",  # 测试跳过酒店
    ]

    for request in test_requests:
        print("=" * 60)
        print(f"用户请求: {request}")
        print("=" * 60)

        # 处理请求
        result = await session.chat(request)

        # 打印思考链
        print("\n📊 Agent 思考过程:")
        await session.print_thought_chain()

        # 打印结果
        print("\n📝 最终回复:")
        print(result.get('reply', ''))

        if result.get('plan'):
            print("\n🗓️ 行程摘要:")
            plan = result['plan']
            for day in plan.get('days', []):
                day_idx = day.get('day_index', 0) + 1
                attractions = [a.get('name') for a in day.get('attractions', [])]
                print(f"  第{day_idx}天: {', '.join(attractions) if attractions else '暂无景点'}")


async def demo_thought_chain():
    """专门演示思考链"""
    print("=" * 60)
    print("🧠 思考链演示")
    print("=" * 60)

    os.environ['USE_REACT_AGENT'] = 'true'

    session = ReActChatSession()
    await session.initialize()

    # 一个会触发多轮推理的请求
    await session.chat("帮我规划从上海到北京的三天行程")

    # 获取思考链
    thoughts = await session.get_thought_chain()

    print("\n完整的思考链记录：")
    print("-" * 60)

    for t in thoughts:
        print(f"\n📌 Step {t.get('step', '?')}")
        print(f"   💭 思考: {t.get('thought', '')[:80]}...")
        print(f"   🎯 行动: {t.get('action', '')}")
        print(f"   📝 原因: {t.get('action_reason', '')[:60]}...")
        print(f"   👁️ 观察: {t.get('observation', '')[:80]}...")
        print(f"   🔄 反思: {t.get('reflection', '')[:80]}...")
        print(f"   📊 置信度: {t.get('confidence', 0):.2f}")


async def interactive_demo():
    """交互式演示"""
    print("=" * 60)
    print("🎮 交互式 ReAct Agent")
    print("=" * 60)
    print("输入 'exit' 退出, 'thoughts' 查看思考链")
    print("-" * 60)

    os.environ['USE_REACT_AGENT'] = 'true'

    session = ReActChatSession()
    await session.initialize()

    while True:
        try:
            user_input = input("\n👤 你: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\n🤖 再见！")
                break

            if user_input.lower() == 'thoughts':
                await session.print_thought_chain()
                continue

            # 处理消息
            print("\n🤖 处理中...")
            result = await session.chat(user_input)

            print(f"\n🤖 回复: {result.get('reply', '')}")

            if result.get('plan'):
                print("\n📅 行程已生成！")

        except KeyboardInterrupt:
            print("\n\n👋 已取消")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    # Windows 控制台 UTF-8 支持
    if sys.platform == 'win32':
        import io
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        except:
            pass

    # 选择演示模式
    print("\n选择演示模式:")
    print("1. 完整演示 (推荐)")
    print("2. 思考链演示")
    print("3. 交互式演示")

    choice = input("\n请输入选项 (1/2/3): ").strip()

    if choice == '1':
        asyncio.run(demo_react_agent())
    elif choice == '2':
        asyncio.run(demo_thought_chain())
    elif choice == '3':
        asyncio.run(interactive_demo())
    else:
        print("默认运行完整演示...")
        asyncio.run(demo_react_agent())