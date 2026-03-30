"""多轮对话旅行规划 Agent

支持对话式交互，用户可以通过自然对话描述需求

使用方式:
    from backend.agent import ChatSession

    session = ChatSession()
    reply = await session.chat("我想去北京玩几天")  # 机器人追问日期
    reply = await session.chat("下周出发，玩3天")    # 继续收集信息
    reply = await session.chat("是的，生成吧")       # 生成行程
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
from backend.agent.state import ChatAgentState, create_initial_state, REQUIRED_FIELDS
from backend.agent.nodes import (
    create_attraction_node,
    create_weather_node,
    create_hotel_node,
    plan_trip_node,
    parse_intent_node,
    adjust_plan_node,
    greeting_node,
    requirement_analyzer_node,
    response_generator_node,
    confirm_check_node,
    stage_router_node,
)
from backend.model import TripPlan, TripRequest
from backend.config.settings import settings

# 设置环境变量
os.environ["OPENAI_API_KEY"] = settings.deepseek_api_key or "sk-placeholder"

# 确认关键词（从统一配置读取）
CONFIRM_KEYWORDS = settings.confirm_keywords

# 调试模式
if settings.debug:
    os.environ["LANGCHAIN_DEBUG"] = "true"


# ===================== 对话式 Agent 系统 =====================

class ChatAgentSystem:
    """对话式旅行规划系统

    支持:
    - 对话收集需求
    - 自动分析信息完整性
    - 生成行程
    - 多轮调整
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
        self.chat_graph = None
        self.plan_graph = None
        self.checkpointer = MemorySaver()

    async def initialize(self):
        """初始化 MCP 工具和 Agent"""
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

            # 创建对话流程图
            self.chat_graph = self._create_chat_graph()
            # 创建规划流程图
            self.plan_graph = self._create_plan_graph()

        except Exception as e:
            print(f"[FAIL] MCP 初始化失败: {str(e)}")
            raise

    def _create_chat_graph(self) -> StateGraph:
        """构建对话流程图"""
        workflow = StateGraph(ChatAgentState)

        # 对话节点
        async def analyzer_node(state):
            return await requirement_analyzer_node(self.llm, state)

        async def response_node(state):
            return await response_generator_node(self.llm, state)

        workflow.add_node("greeting", greeting_node)
        workflow.add_node("analyzer", analyzer_node)
        workflow.add_node("response", response_node)

        # 设置入口点
        workflow.set_entry_point("greeting")

        # 添加边
        workflow.add_edge("greeting", END)  # 问候后等待用户输入
        workflow.add_edge("analyzer", "response")
        workflow.add_edge("response", END)  # 回复后等待用户输入

        return workflow.compile(checkpointer=self.checkpointer)

    def _create_plan_graph(self) -> StateGraph:
        """构建规划流程图（生成行程）"""
        workflow = StateGraph(ChatAgentState)

        # 专家节点
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

        # 规划节点
        async def plan_node(state):
            return await plan_trip_node(self.llm, state)

        workflow.add_node("plan_trip", plan_node)

        # 执行流程
        workflow.set_entry_point("attraction_expert")
        workflow.add_edge("attraction_expert", "weather_expert")
        workflow.add_edge("weather_expert", "hotel_expert")
        workflow.add_edge("hotel_expert", "plan_trip")
        workflow.add_edge("plan_trip", END)

        return workflow.compile(checkpointer=self.checkpointer)

    async def generate_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """根据收集的信息生成行程"""
        print(f"\n[Planning] 开始生成行程: {state.get('city')}, {state.get('start_date')} - {state.get('end_date')}")
        result = await self.plan_graph.ainvoke(state)
        return result

    async def adjust_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """调整现有行程"""
        return await adjust_plan_node(self.llm, state)

    async def parse_intent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析用户意图"""
        return await parse_intent_node(self.llm, state)


# ===================== 对话会话管理 =====================

class ChatSession:
    """对话式会话管理

    使用方式:
        session = ChatSession()
        reply = await session.chat("我想去北京")
        reply = await session.chat("下周出发")
        ...
    """

    def __init__(self):
        self.system = ChatAgentSystem()
        self.thread_id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.thread_id}}
        self._initialized = False
        self._has_sent_greeting = False

    async def initialize(self):
        """初始化会话"""
        if not self._initialized:
            await self.system.initialize()
            self._initialized = True

    async def start(self) -> Dict[str, Any]:
        """开始会话，返回问候消息"""
        await self.initialize()

        if not self._has_sent_greeting:
            # 创建初始状态并获取问候
            initial_state = create_initial_state()
            result = await self.system.chat_graph.ainvoke(initial_state, self.config)
            self._has_sent_greeting = True

            return {
                "reply": result.get('bot_reply', "您好！请告诉我您的旅行需求。"),
                "stage": "greeting",
                "collected_info": {},
                "missing_fields": REQUIRED_FIELDS.copy(),
                "plan": None
            }

        # 如果已发送问候，返回当前状态
        current_state = await self.system.chat_graph.aget_state(self.config)
        return self._build_response(current_state.values)

    async def chat(self, user_message: str) -> Dict[str, Any]:
        """处理用户消息，返回回复

        Args:
            user_message: 用户输入的消息

        Returns:
            包含 reply, stage, collected_info, missing_fields, plan 的字典
        """
        await self.initialize()

        # 获取当前状态
        current_state = await self.system.chat_graph.aget_state(self.config)
        current_values = current_state.values

        stage = current_values.get('conversation_stage', 'greeting')
        collected_info = current_values.get('collected_info', {})
        missing_fields = current_values.get('missing_fields', REQUIRED_FIELDS.copy())
        ready_to_plan = current_values.get('ready_to_plan', False)
        current_plan = current_values.get('final_plan')

        print(f"\n[Chat] 收到消息: {user_message}, 当前阶段: {stage}")

        # 如果已有行程，处理调整请求
        if current_plan:
            return await self._handle_plan_adjustment(user_message, current_values)

        # 检查是否是确认生成
        if stage == "confirming" and ready_to_plan:
            confirm_result = await confirm_check_node({"user_feedback": user_message})
            if confirm_result == "confirmed":
                # 用户确认，开始生成行程
                return await self._generate_and_return(collected_info, current_values)

        # 分析用户消息
        analyze_input = {
            **current_values,
            "user_feedback": user_message,
            "collected_info": collected_info,
            "missing_fields": missing_fields,
        }

        result = await self.system.chat_graph.ainvoke(analyze_input, self.config)
        new_state = await self.system.chat_graph.aget_state(self.config)

        return self._build_response(new_state.values)

    async def _generate_and_return(self, collected_info: Dict[str, Any], current_values: Dict[str, Any]) -> Dict[str, Any]:
        """生成行程并返回结果"""
        print("\n[Generating] 用户确认，开始生成行程...")

        # 构建规划输入
        plan_input = {
            "city": collected_info.get('city', ''),
            "start_date": collected_info.get('start_date', ''),
            "end_date": collected_info.get('end_date', ''),
            "interests": collected_info.get('interests', []),
            "budget_per_day": collected_info.get('budget_per_day'),
            "accommodation_type": collected_info.get('accommodation_type'),
            "transportation_mode": None,
            # 保持其他状态
            "conversation_stage": "planning",
            "collected_info": collected_info,
            "missing_fields": [],
            "ready_to_plan": True,
            "user_confirmed": True,
        }

        # 执行规划
        plan_result = await self.system.generate_plan(plan_input)
        final_plan = plan_result.get('final_plan')

        # 更新对话状态
        await self.system.chat_graph.aupdate_state(
            self.config,
            {
                "final_plan": final_plan,
                "conversation_stage": "refining",
                "bot_reply": "行程已生成！您可以查看并提出调整建议，或者输入'确认'完成规划。"
            }
        )

        return {
            "reply": "行程已生成！您可以查看并提出调整建议，或者输入'确认'完成规划。",
            "stage": "refining",
            "collected_info": collected_info,
            "missing_fields": [],
            "plan": final_plan
        }

    async def _handle_plan_adjustment(self, user_message: str, current_values: Dict[str, Any]) -> Dict[str, Any]:
        """处理行程调整请求"""
        current_plan = current_values.get('final_plan')

        # 检查是否确认满意
        if user_message.strip() in CONFIRM_KEYWORDS:
            await self.system.chat_graph.aupdate_state(
                self.config,
                {"conversation_stage": "done", "is_satisfied": True}
            )
            return {
                "reply": "感谢您的确认！祝您旅途愉快！如需新的规划，请告诉我。",
                "stage": "done",
                "collected_info": current_values.get('collected_info', {}),
                "missing_fields": [],
                "plan": current_plan
            }

        # 解析意图
        intent_state = {
            "user_feedback": user_message,
            "final_plan": current_plan
        }
        intent_result = await self.system.parse_intent(intent_state)
        intent = intent_result.get('intent')

        if intent == 'confirm':
            return {
                "reply": "感谢您的确认！祝您旅途愉快！",
                "stage": "done",
                "collected_info": current_values.get('collected_info', {}),
                "missing_fields": [],
                "plan": current_plan
            }

        if intent not in ['modify_attractions', 'modify_hotels', 'modify_schedule']:
            # 无法理解，生成友好回复
            return {
                "reply": "抱歉，我不太理解您的需求。您可以尝试这样说：'第一天景点太多，减少一些' 或 '换个离景点近的酒店'",
                "stage": "refining",
                "collected_info": current_values.get('collected_info', {}),
                "missing_fields": [],
                "plan": current_plan
            }

        # 执行调整
        adjust_state = {
            "final_plan": current_plan,
            "intent": intent,
            "target_days": intent_result.get('target_days', []),
            "action": intent_result.get('action'),
            "details": intent_result.get('details'),
            "iteration_count": current_values.get('iteration_count', 0) + 1
        }

        adjust_result = await self.system.adjust_plan(adjust_state)
        new_plan = adjust_result.get('final_plan')

        if new_plan:
            await self.system.chat_graph.aupdate_state(
                self.config,
                {
                    "final_plan": new_plan,
                    "iteration_count": adjust_state['iteration_count'],
                    "bot_reply": f"已根据您的反馈调整行程：{intent_result.get('details')}"
                }
            )

            return {
                "reply": f"已根据您的反馈调整行程：{intent_result.get('details')}。您可以继续提出调整建议，或输入'确认'完成。",
                "stage": "refining",
                "collected_info": current_values.get('collected_info', {}),
                "missing_fields": [],
                "plan": new_plan
            }

        return {
            "reply": "抱歉，调整失败了。请尝试换一种方式描述您的需求。",
            "stage": "refining",
            "collected_info": current_values.get('collected_info', {}),
            "missing_fields": [],
            "plan": current_plan
        }

    def _build_response(self, state_values: Dict[str, Any]) -> Dict[str, Any]:
        """构建响应字典"""
        return {
            "reply": state_values.get('bot_reply', "请告诉我您的旅行需求。"),
            "stage": state_values.get('conversation_stage', 'collecting'),
            "collected_info": state_values.get('collected_info', {}),
            "missing_fields": state_values.get('missing_fields', []),
            "plan": state_values.get('final_plan')
        }

    async def get_current_state(self) -> Dict[str, Any]:
        """获取当前会话状态"""
        state = await self.system.chat_graph.aget_state(self.config)
        return state.values


# ===================== 兼容旧版本的会话类 =====================

class TripChatSession(ChatSession):
    """兼容旧版本的会话类

    保持原有的 start/feedback 方法兼容性
    """

    async def start(self, request: TripRequest = None) -> Optional[Dict[str, Any]]:
        """开始规划行程

        Args:
            request: TripRequest 对象（可选，如果不提供则进入对话模式）

        Returns:
            规划结果字典，或问候消息字典
        """
        await self.initialize()

        if request:
            # 表单模式：直接生成行程
            inputs = create_initial_state(request)
            result = await self.system.generate_plan(inputs)

            # 更新状态
            await self.system.chat_graph.aupdate_state(
                self.config,
                {
                    "final_plan": result.get('final_plan'),
                    "conversation_stage": "refining",
                    "collected_info": {
                        "city": request.city,
                        "start_date": request.start_date,
                        "end_date": request.end_date,
                        "interests": request.interests,
                    },
                    "ready_to_plan": True,
                }
            )

            return result.get('final_plan')

        else:
            # 对话模式：返回问候
            result = await super().start()
            return result.get('reply')

    async def feedback(self, user_input: str) -> Optional[Dict[str, Any]]:
        """提交用户反馈（兼容旧版本）"""
        result = await self.chat(user_input)
        return result.get('plan')

    async def get_current_plan(self) -> Optional[Dict[str, Any]]:
        """获取当前行程"""
        state = await self.system.chat_graph.aget_state(self.config)
        return state.values.get('final_plan')

    def format_plan(self, plan: Optional[Dict[str, Any]]) -> str:
        """格式化行程输出"""
        if not plan:
            return "暂无行程"
        import json
        return json.dumps(plan, ensure_ascii=False, indent=2)


# ===================== 交互式主程序 =====================

async def interactive_main():
    """交互式对话主程序"""
    print("=" * 60)
    print("Travel Planning Agent - 对话模式")
    print("=" * 60)

    session = ChatSession()

    try:
        # 获取问候消息
        greeting = await session.start()
        print(f"\n[助手]: {greeting['reply']}")

        while True:
            user_input = input("\n[您]: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\n[助手]: 再见！祝您旅途愉快！")
                break

            # 处理消息
            result = await session.chat(user_input)

            print(f"\n[助手]: {result['reply']}")

            # 如果有行程，显示摘要
            if result.get('plan'):
                plan = result['plan']
                print("\n" + "=" * 40)
                print("行程摘要:")
                for day in plan.get('days', []):
                    day_idx = day.get('day_index', 0) + 1
                    attractions = [a.get('name') for a in day.get('attractions', [])]
                    print(f"  第{day_idx}天: {', '.join(attractions) if attractions else '暂无景点'}")
                print("=" * 40)

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