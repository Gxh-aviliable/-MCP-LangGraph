"""多轮对话旅行规划 Agent

支持对话式交互，用户可以通过自然对话描述需求

架构设计：
- 共享资源层（MCP 工具、LLM）：全局单例，所有会话共用
- 状态层（LangGraph、Checkpointer）：每个会话独立，保证对话隔离

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
import json
from typing import Dict, Any, Optional, List

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
    create_transport_node_v3,
    create_smart_planning_graph,
    optional_guidance_node,
)
# 【新增】ReAct Agent 图
from backend.agent.graphs import create_react_agent_graph
from backend.agent.router import analyze_query_complexity, get_scenario_description
from backend.model import TripPlan, TripRequest
from backend.config.settings import settings

# 设置环境变量（用于 LangChain）
os.environ["OPENAI_API_KEY"] = settings.dashscope_api_key or "sk-placeholder"

# 确认关键词（从统一配置读取）
CONFIRM_KEYWORDS = settings.confirm_keywords

# 调试模式
if settings.debug:
    os.environ["LANGCHAIN_DEBUG"] = "true"
    print(f"[Config] 主模型: {settings.primary_model}")


# ===================== 共享资源管理器（方案C核心） =====================

class SharedResourceManager:
    """共享资源管理器 - 全局单例

    架构设计理念：
    1. MCP 工具连接是 I/O 操作，天然支持并发调用，适合共享
    2. LLM 实例是无状态的，适合共享
    3. 共享后，新会话创建只需毫秒级（无需重新初始化 MCP）

    使用方式：
        manager = SharedResourceManager()
        await manager.initialize()  # 启动时调用一次

        # 所有会话共用
        tools = manager.get_tools()
        llm = manager.get_llm()
    """

    _instance: Optional['SharedResourceManager'] = None
    _initialized: bool = False

    def __new__(cls):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: List = []
            cls._instance._llm: Optional[ChatOpenAI] = None
            cls._instance._amap_key: Optional[str] = None
            cls._instance._client: Optional[MultiServerMCPClient] = None
            cls._instance._extra_clients: Dict = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'SharedResourceManager':
        """获取全局实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    async def ensure_initialized(cls) -> 'SharedResourceManager':
        """确保已初始化，返回实例

        使用方式：
            manager = await SharedResourceManager.ensure_initialized()
            tools = manager.get_tools()
        """
        instance = cls.get_instance()
        if not cls._initialized:
            await instance.initialize()
        return instance

    async def initialize(self):
        """初始化共享资源（MCP 工具、LLM）

        只需要在应用启动时调用一次。
        后续所有会话共用这些资源。
        """
        if SharedResourceManager._initialized:
            print("[SharedResources] 已初始化，跳过")
            return

        print("[SharedResources] 开始初始化...")

        self._amap_key = settings.amap_maps_api_key
        if not self._amap_key:
            raise ValueError("AMAP_MAPS_API_KEY 未设置")

        # === 1. 初始化 LLM（共享给所有会话） ===
        print("[SharedResources] 步骤1: 初始化 LLM...")
        self._llm = ChatOpenAI(
            model=settings.primary_model,
            openai_api_key=settings.dashscope_api_key,
            openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=settings.llm_temperature
        )
        print(f"[SharedResources] LLM 已初始化: {settings.primary_model}")

        # === 2. 读取 MCP 配置文件 ===
        print("[SharedResources] 步骤2: 读取 MCP 配置文件...")
        from pathlib import Path
        config_path = Path(__file__).parent.parent / "config" / "mcp_config.json"

        mcp_servers_config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                mcp_config = json.load(f)
                for server in mcp_config.get("mcp_servers", []):
                    if server.get("enabled") and server.get("url") and not server["url"].startswith("${"):
                        mcp_servers_config[server["name"]] = server
        print(f"[SharedResources] 配置文件读取完成，可选服务器: {list(mcp_servers_config.keys())}")

        # === 3. 初始化高德地图 MCP (stdio 方式) ===
        print("[SharedResources] 步骤3: 初始化高德地图 MCP...")

        server_config = {
            "amap": {
                "command": "uvx",
                "args": ["amap-mcp-server"],
                "transport": "stdio",
                "env": {
                    **os.environ,
                    "AMAP_MAPS_API_KEY": self._amap_key
                }
            }
        }

        try:
            print("[MCP] 正在初始化高德地图工具...")
            self._client = MultiServerMCPClient(server_config)
            self._tools = await asyncio.wait_for(
                self._client.get_tools(),
                timeout=60.0  # 增加到 60 秒
            )

            if not self._tools:
                raise ValueError("未能加载高德地图工具")

            tool_names = [t.name for t in self._tools]
            print(f"[OK] 高德地图工具加载成功 ({len(tool_names)} 个): {tool_names}")

        except asyncio.TimeoutError:
            print(f"[FAIL] 高德地图 MCP 初始化超时（60秒）")
            raise TimeoutError("高德地图 MCP 初始化超时，请检查 uvx 是否正确安装")
        except Exception as e:
            print(f"[FAIL] 高德地图 MCP 初始化失败: {str(e)}")
            raise

        # === 4. 连接可选 MCP 服务器 ===
        print("[SharedResources] 步骤4: 连接可选 MCP 服务器...")

        for name, server in mcp_servers_config.items():
            url = server.get("url", "")
            if url and not url.startswith("${"):
                print(f"[MCP] 尝试连接服务器: {name}, URL: {url}")
                try:
                    transport_type = server.get("transport", "sse")

                    single_server_config = {
                        name: {
                            "url": url,
                            "transport": transport_type
                        }
                    }
                    if server.get("headers"):
                        single_server_config[name]["headers"] = server["headers"]

                    print(f"[MCP] 配置: transport={transport_type}")

                    single_client = MultiServerMCPClient(single_server_config)
                    new_tools = await asyncio.wait_for(
                        single_client.get_tools(),
                        timeout=20.0
                    )

                    if new_tools:
                        self._tools.extend(new_tools)
                        self._extra_clients[name] = single_client
                        print(f"[OK] 服务器 {name} 连接成功，获取 {len(new_tools)} 个工具: {[t.name for t in new_tools]}")
                    else:
                        print(f"[WARN] 服务器 {name} 未返回工具")

                except asyncio.TimeoutError:
                    print(f"[WARN] 服务器 {name} 连接超时（20秒），跳过")
                except Exception as e:
                    print(f"[WARN] 服务器 {name} 连接失败: {str(e)[:200]}")

        # 打印最终加载的工具
        final_tool_names = [t.name for t in self._tools]
        print(f"[SharedResources] 总共加载 {len(final_tool_names)} 个共享工具")

        # 标记已初始化
        SharedResourceManager._initialized = True
        print("[SharedResources] [OK] 初始化完成!")

    def get_tools(self) -> List:
        """获取共享的工具列表"""
        return self._tools

    def get_llm(self) -> ChatOpenAI:
        """获取共享的 LLM 实例"""
        return self._llm

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return SharedResourceManager._initialized

    @classmethod
    def reset(cls):
        """重置共享资源（用于测试或重新加载配置）

        注意：这会断开所有 MCP 连接
        """
        if cls._instance:
            cls._instance._tools = []
            cls._instance._client = None
            cls._instance._extra_clients = {}
        cls._instance = None
        cls._initialized = False
        print("[SharedResources] 已重置")


# ===================== 对话会话管理（使用共享资源） =====================

class ChatSession:
    """对话式会话管理

    架构设计：
    - 使用共享的 MCP 工具和 LLM（资源高效）
    - 每个会话有独立的 LangGraph 和 Checkpointer（状态隔离）
    - 新会话创建只需毫秒级

    使用方式:
        session = ChatSession()
        await session.initialize()  # 毫秒级，使用共享资源
        reply = await session.chat("我想去北京")
    """

    def __init__(self):
        # 共享资源（从全局管理器获取）
        self.shared_resources: Optional[SharedResourceManager] = None
        self.tools: List = []
        self.llm: Optional[ChatOpenAI] = None

        # 独立资源（每个会话独有）
        self.thread_id = str(uuid.uuid4())
        self.checkpointer = MemorySaver()  # 独立的状态存储
        self.chat_graph = None  # 独立的对话图
        self.plan_graph = None  # 独立的规划图
        self.config = {"configurable": {"thread_id": self.thread_id}}

        self._initialized = False
        self._has_sent_greeting = False
        self.agent_mode: str = "smart"  # 保存当前模式

    async def initialize(self, agent_mode: str = "smart"):
        """初始化会话 - 使用共享资源

        Args:
            agent_mode: "smart" 智能规划图, "react" ReAct Agent

        由于 MCP 工具已共享，这里只需：
        1. 获取共享的工具和 LLM（毫秒级）
        2. 创建独立的 LangGraph 和 Checkpointer
        """
        if self._initialized:
            return

        print(f"[ChatSession] 初始化会话 {self.thread_id[:8]}..., 模式: {agent_mode}")

        # 保存模式
        self.agent_mode = agent_mode

        # 获取共享资源
        self.shared_resources = await SharedResourceManager.ensure_initialized()
        self.tools = self.shared_resources.get_tools()
        self.llm = self.shared_resources.get_llm()

        # 创建独立的 LangGraph（每个会话需要独立的 checkpointer）
        self.chat_graph = self._create_chat_graph()
        self.plan_graph = self._create_plan_graph(agent_mode)

        self._initialized = True
        print(f"[ChatSession] [OK] 会话 {self.thread_id[:8]} 初始化完成 (模式: {agent_mode})")

    def _create_chat_graph(self) -> StateGraph:
        """构建对话流程图（独立实例）"""
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
        workflow.set_entry_point("analyzer")

        # 添加边
        workflow.add_edge("analyzer", "response")
        workflow.add_edge("response", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def _create_plan_graph(self, agent_mode: str = "smart") -> StateGraph:
        """构建规划流程图（独立实例，使用共享工具）

        Args:
            agent_mode: "smart" 智能规划图, "react" ReAct Agent
        """
        if agent_mode == "react":
            print("[ChatSession] 使用 ReAct Agent 图（动态推理模式）")
            return create_react_agent_graph(self.llm, self.tools)
        else:
            print("[ChatSession] 使用智能规划图（高效流水线模式）")
            return create_smart_planning_graph(self.llm, self.tools)

    async def start(self) -> Dict[str, Any]:
        """开始会话，返回问候消息"""
        await self.initialize()

        if not self._has_sent_greeting:
            from backend.prompts import GREETING_MESSAGE
            self._has_sent_greeting = True

            # 初始化状态
            initial_state = create_initial_state()
            await self.chat_graph.aupdate_state(self.config, initial_state)

            return {
                "reply": GREETING_MESSAGE,
                "stage": "greeting",
                "collected_info": {},
                "missing_fields": REQUIRED_FIELDS.copy(),
                "plan": None
            }

        # 如果已发送问候，返回当前状态
        current_state = await self.chat_graph.aget_state(self.config)
        return self._build_response(current_state.values)

    async def chat(self, user_message: str) -> Dict[str, Any]:
        """处理用户消息，返回回复"""
        await self.initialize()

        # 获取当前状态
        current_state = await self.chat_graph.aget_state(self.config)
        current_values = current_state.values

        stage = current_values.get('conversation_stage', 'greeting')
        collected_info = current_values.get('collected_info', {})
        missing_fields = current_values.get('missing_fields', REQUIRED_FIELDS.copy())
        ready_to_plan = current_values.get('ready_to_plan', False)
        current_plan = current_values.get('final_plan')
        optional_collected = current_values.get('optional_collected', False)

        print(f"\n[Chat] 会话 {self.thread_id[:8]} 收到消息: {user_message[:30]}..., 当前阶段: {stage}")

        # 如果已有行程，处理调整请求
        if current_plan:
            return await self._handle_plan_adjustment(user_message, current_values)

        # 处理可选参数引导阶段
        if stage == "optional_collecting" and not optional_collected:
            return await self._handle_optional_collection(user_message, current_values)

        # 检查是否是确认生成
        if stage == "confirming" and ready_to_plan:
            # 【修复】先检查用户是否在补充可选参数
            if self._contains_optional_info(user_message):
                # 提取并更新可选参数
                updated_info = await self._extract_optional_from_message(user_message, collected_info)
                await self.chat_graph.aupdate_state(self.config, {"collected_info": updated_info})
                return {
                    "reply": f"好的，已记录您的信息。现在为您生成行程吗？",
                    "stage": "confirming",
                    "collected_info": updated_info,
                    "missing_fields": [],
                    "plan": None
                }

            # 检查是否确认生成
            confirm_result = await confirm_check_node({"user_feedback": user_message})
            if confirm_result == "confirmed":
                return await self._generate_and_return(collected_info, current_values)
            # 用户没有确认，保持当前状态
            return {
                "reply": "请确认是否生成行程（回复'是'或'确认'）",
                "stage": "confirming",
                "collected_info": collected_info,
                "missing_fields": [],
                "plan": None
            }

        # 分析用户消息
        analyze_input = {
            **current_values,
            "user_feedback": user_message,
            "collected_info": collected_info,
            "missing_fields": missing_fields,
        }

        result = await self.chat_graph.ainvoke(analyze_input, self.config)
        new_state = await self.chat_graph.aget_state(self.config)

        return self._build_response(new_state.values)

    def _contains_optional_info(self, message: str) -> bool:
        """判断消息是否包含可选参数信息"""
        keywords = {
            'interests': ['喜欢', '景点', '公园', '博物馆', '古迹', '美食', '购物', '想去', '天安门', '故宫', '长城'],
            'budget': ['预算', '钱', '元', '块', '花费', '2k', '3k'],
            'accommodation': ['酒店', '住宿', '住'],
            'transport': ['火车', '飞机', '高铁', '自驾']
        }
        message_lower = message.lower()
        for category, words in keywords.items():
            if any(word in message_lower for word in words):
                return True
        return False

    async def _extract_optional_from_message(self, message: str, collected_info: Dict) -> Dict:
        """从消息中提取可选参数"""
        import re

        updated = {**collected_info}

        # 提取预算
        budget_match = re.search(r'(\d+)[kK]|\b(\d{3,})\s*(元|块)', message)
        if budget_match:
            if budget_match.group(1):  # Xk format
                budget = int(budget_match.group(1)) * 1000
            else:
                budget = int(budget_match.group(2))
            updated['budget_per_day'] = budget // 3 if budget > 1000 else budget  # 总预算转日均

        # 提取兴趣
        interest_keywords = ['天安门', '故宫', '长城', '颐和园', '博物馆', '公园', '美食']
        found_interests = [kw for kw in interest_keywords if kw in message]
        if found_interests:
            existing = updated.get('interests', [])
            updated['interests'] = list(set(existing + found_interests))

        return updated

    async def _handle_optional_collection(self, user_message: str, current_values: Dict[str, Any]) -> Dict[str, Any]:
        """处理可选参数收集阶段"""
        print(f"\n[Optional] 引导用户填写可选参数...")

        # 调用可选参数引导节点
        optional_input = {
            **current_values,
            "user_feedback": user_message,
        }

        result = await optional_guidance_node(self.llm, optional_input)

        # 更新状态
        await self.chat_graph.aupdate_state(self.config, result)

        # 如果引导已完成，检查是否可以直接生成
        if result.get('optional_collected'):
            # 如果用户明确跳过或说"直接生成"
            if result.get('optional_skipped'):
                confirm_result = await confirm_check_node({"user_feedback": user_message})
                if confirm_result == "confirmed":
                    return await self._generate_and_return(result.get('collected_info', {}), current_values)

        return self._build_response(result)

    async def _generate_and_return(self, collected_info: Dict[str, Any], current_values: Dict[str, Any]) -> Dict[str, Any]:
        """生成行程并返回结果"""
        print(f"\n[Generating] 会话 {self.thread_id[:8]} 开始生成行程...")

        # 构建规划输入
        plan_input = {
            "origin": collected_info.get('origin', ''),
            "city": collected_info.get('city', ''),
            "start_date": collected_info.get('start_date', ''),
            "end_date": collected_info.get('end_date', ''),
            "interests": collected_info.get('interests', []),
            "budget_per_day": collected_info.get('budget_per_day'),
            "accommodation_type": collected_info.get('accommodation_type'),
            "transportation_mode": None,
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "transport_data": [],
            "conversation_stage": "planning",
            "collected_info": collected_info,
            "missing_fields": [],
            "ready_to_plan": True,
            "user_confirmed": True,
        }

        # 执行规划
        plan_result = await self.plan_graph.ainvoke(plan_input)
        final_plan = plan_result.get('final_plan')

        # 更新对话状态
        await self.chat_graph.aupdate_state(
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
        """处理行程调整请求 - 根据模式选择处理方式"""
        current_plan = current_values.get('final_plan')

        # 检查是否确认满意（两种模式通用）
        if user_message.strip() in CONFIRM_KEYWORDS:
            await self.chat_graph.aupdate_state(
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

        # 【核心改动】根据模式选择处理方式
        if self.agent_mode == "react":
            return await self._handle_react_feedback(user_message, current_values)
        else:
            return await self._handle_smart_feedback(user_message, current_values)

    async def _handle_smart_feedback(self, user_message: str, current_values: Dict[str, Any]) -> Dict[str, Any]:
        """智能模式处理反馈 - 直接修改"""
        current_plan = current_values.get('final_plan')

        # 解析意图
        intent_state = {
            "user_feedback": user_message,
            "final_plan": current_plan
        }
        intent_result = await parse_intent_node(self.llm, intent_state)
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

        adjust_result = await adjust_plan_node(self.llm, adjust_state)
        new_plan = adjust_result.get('final_plan')

        if new_plan:
            await self.chat_graph.aupdate_state(
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

    async def _handle_react_feedback(self, user_message: str, current_values: Dict[str, Any]) -> Dict[str, Any]:
        """ReAct 模式处理反馈 - 重新进入推理循环"""
        print(f"\n[ReAct Feedback] 用户反馈: {user_message}")

        # 构建新的规划输入，保留已有数据
        plan_input = {
            **current_values,
            "user_feedback": user_message,
            "adjustment_request": True,      # 标记这是调整请求
            "iteration_count": 0,            # 重置迭代计数
            "should_continue": True,         # 允许继续推理
            "next_action": "",               # 清空上一步行动
            "quality_score": 0.0,            # 重置质量分数
            "thoughts": [],                  # 清空思考链，开始新的推理
        }

        # 重新运行 ReAct 图
        print("[ReAct Feedback] 重新进入推理循环...")
        result = await self.plan_graph.ainvoke(plan_input)

        new_plan = result.get('final_plan')
        thoughts = result.get('thoughts', [])

        # 更新对话状态
        await self.chat_graph.aupdate_state(
            self.config,
            {
                "final_plan": new_plan,
                "thoughts": thoughts,
                "conversation_stage": "refining",
            }
        )

        # 生成回复
        reply = self._generate_feedback_reply(thoughts, new_plan)
        return {
            "reply": reply,
            "stage": "refining",
            "collected_info": current_values.get('collected_info', {}),
            "missing_fields": [],
            "plan": new_plan
        }

    def _generate_feedback_reply(self, thoughts: List, plan: Dict) -> str:
        """根据思考链生成回复"""
        if thoughts:
            last_thought = thoughts[-1]
            action = last_thought.get('action', '')
            reflection = last_thought.get('reflection', '')

            if action == 'adjust_plan':
                return f"已根据您的反馈调整行程。{reflection} 您可以继续提出建议，或输入'确认'完成。"
            elif action == 'regenerate':
                return f"已重新规划行程。{reflection} 您可以继续提出建议，或输入'确认'完成。"
            elif action == 'refine_plan':
                return f"已优化行程。{reflection} 您可以继续提出建议，或输入'确认'完成。"

        return "行程已调整，请查看并提出您的建议。"

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
        state = await self.chat_graph.aget_state(self.config)
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
            result = await self.plan_graph.ainvoke(inputs)

            await self.chat_graph.aupdate_state(
                self.config,
                {
                    "final_plan": result.get('final_plan'),
                    "conversation_stage": "refining",
                    "collected_info": {
                        "origin": request.origin,
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
        state = await self.chat_graph.aget_state(self.config)
        return state.values.get('final_plan')

    def format_plan(self, plan: Optional[Dict[str, Any]]) -> str:
        """格式化行程输出"""
        if not plan:
            return "暂无行程"
        return json.dumps(plan, ensure_ascii=False, indent=2)


# ===================== 兼容旧版本别名 =====================

# 保留 ChatAgentSystem 作为别名，但不再使用（改用 SharedResourceManager）
class ChatAgentSystem:
    """兼容旧版本的别名类

    注意：现在推荐使用 SharedResourceManager 管理共享资源
    这个类保留是为了向后兼容，但内部使用共享资源管理器
    """

    @classmethod
    async def get_shared(cls):
        """获取共享资源"""
        return await SharedResourceManager.ensure_initialized()


# 旧版本类名别名
TripChatSystem = ChatAgentSystem


# ===================== 交互式主程序 =====================

async def interactive_main():
    """交互式对话主程序"""
    print("=" * 60)
    print("Travel Planning Agent - 对话模式")
    print("=" * 60)

    # 先初始化共享资源
    print("\n[启动] 初始化共享资源...")
    await SharedResourceManager.ensure_initialized()
    print("[启动] 共享资源已就绪，开始对话...\n")

    session = ChatSession()
    await session.initialize()

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


# ===================== ReAct Agent 会话类 =====================

class ReActChatSession(ChatSession):
    """ReAct Agent 会话 - 真正的智能推理

    与普通 ChatSession 的区别：
    - 普通 ChatSession：固定流水线，预定义流程
    - ReActChatSession：动态推理，根据结果调整行动

    使用场景：
    - 需要更智能的决策时
    - 需要根据结果动态调整时
    - 需要多轮推理时

    使用方式:
        os.environ['USE_REACT_AGENT'] = 'true'
        session = ReActChatSession()
        await session.initialize()
        result = await session.chat("我想去北京玩三天")
    """

    def __init__(self):
        # 强制使用 ReAct 图
        os.environ['USE_REACT_AGENT'] = 'true'
        super().__init__()

    async def get_thought_chain(self) -> List[Dict[str, Any]]:
        """获取 Agent 的思考链

        这是 ReAct Agent 的核心特性：
        可以查看每一步的思考、行动、观察、反思
        """
        state = await self.chat_graph.aget_state(self.config)
        return state.values.get('thoughts', [])

    async def print_thought_chain(self):
        """打印思考链（用于调试）"""
        thoughts = await self.get_thought_chain()

        if not thoughts:
            print("暂无思考记录")
            return

        print("\n" + "=" * 60)
        print("🧠 Agent 思考链")
        print("=" * 60)

        for t in thoughts:
            step = t.get('step', '?')
            print(f"\n--- Step {step} ---")
            print(f"💭 思考: {t.get('thought', '')[:100]}...")
            print(f"🎯 行动: {t.get('action', '')} ({t.get('action_reason', '')[:50]}...)")
            print(f"👁️ 观察: {t.get('observation', '')[:100]}...")
            print(f"🔄 反思: {t.get('reflection', '')[:100]}...")
            print(f"📊 置信度: {t.get('confidence', 0):.2f}")

        print("\n" + "=" * 60)