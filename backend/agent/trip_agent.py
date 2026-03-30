"""多轮对话旅行规划 Agent

支持持续性对话，用户可以动态调整行程

使用方式:
    from backend.agent import TripChatSession

    session = TripChatSession()
    plan = await session.start(request)
    new_plan = await session.feedback("第一天景点有点多")
"""
import asyncio
import os
import sys
import io
import uuid
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

# 项目内部导入
from backend.agent.state import ChatAgentState, create_initial_state
from backend.agent.nodes import (
    create_attraction_node,
    create_weather_node,
    create_hotel_node,
    plan_trip_node,
    parse_intent_node,
    adjust_plan_node,
)
from backend.model import TripPlan, TripRequest
from backend.config.settings import settings

# 设置环境变量
os.environ["OPENAI_API_KEY"] = settings.deepseek_api_key or "sk-placeholder"

# 调试模式
if settings.debug:
    os.environ["LANGCHAIN_DEBUG"] = "true"


# ===================== 核心系统 =====================

class TripChatSystem:
    """旅行规划系统核心

    负责:
    - 初始化 MCP 工具
    - 创建 LLM 实例
    - 构建 LangGraph 执行图
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model='deepseek-chat',
            api_key=settings.deepseek_api_key,
            base_url='https://api.deepseek.com'
        )
        self.amap_key = settings.amap_maps_api_key
        self.client = None
        self.tools = None
        self.graph = None
        self.checkpointer = MemorySaver()

    async def initialize(self):
        """初始化 MCP 工具"""
        if not self.amap_key:
            raise ValueError("AMAP_MAPS_API_KEY 未设置")

        server_config = {
            "amap": {
                "command": "uvx",
                "args": ["amap-mcp-server"],
                "transport": "stdio",
                "env": {
                    **os.environ,
                    "AMAP_MAPS_API_KEY": self.amap_key
                }
            }
        }

        try:
            self.client = MultiServerMCPClient(server_config)
            self.tools = await self.client.get_tools()

            if not self.tools:
                raise ValueError("未能加载任何工具")

            tool_names = [t.name for t in self.tools]
            print(f"[OK] 成功加载工具: {tool_names}")

            self.graph = self._create_graph()

        except Exception as e:
            print(f"[FAIL] MCP 初始化失败: {str(e)}")
            raise

    def _create_graph(self) -> StateGraph:
        """构建 LangGraph 执行图"""
        workflow = StateGraph(ChatAgentState)

        # 添加专家节点
        workflow.add_node(
            "attraction_expert",
            create_attraction_node(self.llm, self.tools)
        )
        workflow.add_node(
            "weather_expert",
            create_weather_node(self.llm, self.tools)
        )
        workflow.add_node(
            "hotel_expert",
            create_hotel_node(self.llm, self.tools)
        )

        # 添加规划节点 (包装为 async 函数)
        async def plan_node(state):
            return await plan_trip_node(self.llm, state)
        workflow.add_node("plan_trip", plan_node)

        # 构建执行流程
        workflow.set_entry_point("attraction_expert")
        workflow.add_edge("attraction_expert", "weather_expert")
        workflow.add_edge("weather_expert", "hotel_expert")
        workflow.add_edge("hotel_expert", "plan_trip")
        workflow.add_edge("plan_trip", END)

        return workflow.compile(checkpointer=self.checkpointer)

    # ===================== 多轮对话方法 =====================

    async def parse_intent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析用户意图"""
        return await parse_intent_node(self.llm, state)

    async def adjust_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """调整行程"""
        return await adjust_plan_node(self.llm, state)


# ===================== 会话管理 =====================

class TripChatSession:
    """多轮对话会话管理

    使用方式:
        session = TripChatSession()
        plan = await session.start(request)
        new_plan = await session.feedback("第一天景点有点多")
    """

    def __init__(self):
        self.system = TripChatSystem()
        self.thread_id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.thread_id}}
        self._initialized = False

    async def initialize(self):
        """初始化会话"""
        if not self._initialized:
            await self.system.initialize()
            self._initialized = True

    async def start(self, request: TripRequest) -> Optional[Dict[str, Any]]:
        """开始规划行程

        Args:
            request: TripRequest 对象

        Returns:
            规划结果字典，失败返回 None
        """
        await self.initialize()

        inputs = create_initial_state(request)
        result = await self.system.graph.ainvoke(inputs, self.config)

        return result.get('final_plan')

    async def feedback(self, user_input: str) -> Optional[Dict[str, Any]]:
        """提交用户反馈，继续对话

        Args:
            user_input: 用户反馈文本

        Returns:
            调整后的行程，失败返回 None
        """
        current_state = await self.system.graph.aget_state(self.config)
        current_plan = current_state.values.get('final_plan')

        # 用户确认满意
        if user_input.strip() in ['确认', '满意', '好的', '可以', '没问题', 'confirm']:
            return current_plan

        if not current_plan:
            print("[WARN] 暂无行程，无法调整")
            return None

        # 解析意图
        print("[INFO] 解析您的反馈...")
        intent_state = {
            "user_feedback": user_input,
            "final_plan": current_plan
        }

        intent_result = await self.system.parse_intent(intent_state)
        intent = intent_result.get('intent')

        if intent == 'confirm':
            print("[OK] 您对行程满意！")
            return current_plan

        if intent not in ['modify_attractions', 'modify_hotels', 'modify_schedule']:
            print("[WARN] 暂时无法理解您的需求，请换种方式表达")
            return current_plan

        # 执行调整
        adjust_state = {
            "final_plan": current_plan,
            "intent": intent,
            "target_days": intent_result.get('target_days', []),
            "action": intent_result.get('action'),
            "details": intent_result.get('details'),
            "iteration_count": current_state.values.get('iteration_count', 0) + 1
        }

        adjust_result = await self.system.adjust_plan(adjust_state)
        new_plan = adjust_result.get('final_plan')

        if new_plan:
            await self.system.graph.aupdate_state(
                self.config,
                {
                    "final_plan": new_plan,
                    "iteration_count": adjust_state['iteration_count'],
                    "user_feedback": user_input
                }
            )

        return new_plan

    async def get_current_plan(self) -> Optional[Dict[str, Any]]:
        """获取当前行程"""
        state = await self.system.graph.aget_state(self.config)
        return state.values.get('final_plan')

    def format_plan(self, plan: Optional[Dict[str, Any]]) -> str:
        """格式化行程输出"""
        if not plan:
            return "暂无行程"
        import json
        return json.dumps(plan, ensure_ascii=False, indent=2)


# ===================== 交互式主程序 =====================

async def interactive_main():
    """交互式多轮对话主程序"""
    print("=" * 60)
    print("Travel Planning Agent - Multi-turn Dialog")
    print("=" * 60)

    session = TripChatSession()

    try:
        # 获取用户输入
        print("\n请输入您的旅行需求：")
        city = input("城市: ").strip() or "北京"
        start_date = input("开始日期 (YYYY-MM-DD): ").strip() or "2026-03-26"
        end_date = input("结束日期 (YYYY-MM-DD): ").strip() or "2026-03-27"
        interests_str = input("兴趣偏好 (逗号分隔): ").strip() or "历史古迹"
        accommodation = input("住宿类型 (可选): ").strip() or None
        budget = input("每日预算 (可选): ").strip()
        transportation = input("交通方式 (可选): ").strip() or None

        # 构建请求
        request = TripRequest(
            city=city,
            start_date=start_date,
            end_date=end_date,
            interests=[i.strip() for i in interests_str.split(',')],
            accommodation_type=accommodation,
            budget_per_day=int(budget) if budget else None,
            transportation_mode=transportation
        )

        print(f"\n[INFO] 正在为您规划 {city} 的行程...\n")

        # 开始规划
        plan = await session.start(request)

        if not plan:
            print("[FAIL] 规划失败，请重试")
            return

        # 显示行程
        print("=" * 60)
        print("Your Trip Plan:")
        print("=" * 60)
        print(session.format_plan(plan))

        # 多轮对话循环
        print("\n" + "=" * 60)
        print("您可以提出修改意见，例如：")
        print("   - 第一天景点有点多")
        print("   - 酒店换个离景点近的")
        print("   输入 '确认' 或 '满意' 完成规划")
        print("=" * 60)

        while True:
            user_input = input("\n您的反馈: ").strip()

            if not user_input:
                continue

            if user_input in ['确认', '满意', '好的', '可以', '没问题', 'confirm', 'exit', 'quit', 'q']:
                print("\n[OK] 行程规划完成！祝您旅途愉快！")
                break

            print("\n[INFO] 正在调整行程...")
            plan = await session.feedback(user_input)

            if plan:
                print("\n" + "=" * 60)
                print("调整后的行程：")
                print("=" * 60)
                print(session.format_plan(plan))
            else:
                print("[WARN] 调整失败，请重试")

    except KeyboardInterrupt:
        print("\n\n[INFO] 已取消")
    except Exception as e:
        print(f"\n[FAIL] 错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Windows 控制台 UTF-8 支持
    if sys.platform == 'win32':
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        except (ValueError, AttributeError):
            pass
    asyncio.run(interactive_main())