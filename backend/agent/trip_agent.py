"""多轮对话旅行规划 Agent

支持持续性对话，用户可以动态调整行程
"""
import asyncio
import os
import operator
import sys
import io
import uuid
from pathlib import Path
from datetime import datetime

# Windows 控制台 UTF-8 支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from typing import Annotated, List, TypedDict, Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.callbacks import BaseCallbackHandler

# 项目内部导入
sys.path.insert(0, str(Path(__file__).parent.parent))
from model.schemas import TripPlan, TripRequest, Attraction, WeatherInfo, Hotel
from config.settings import settings

# 设置环境变量（DeepSeek API 兼容 OpenAI SDK）
os.environ["OPENAI_API_KEY"] = settings.deepseek_api_key or "sk-placeholder"

# 开启 LangChain 调试模式
if settings.debug:
    os.environ["LANGCHAIN_DEBUG"] = "true"
    print("🔍 调试模式已开启")


# ===================== Prompt 定义 =====================

ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。你的任务是根据指定的城市和用户偏好，利用专业搜索工具获取真实、准确的景点信息。

**核心准则 (Core Principles):**
1. **工具依赖性**: 你严禁基于自身的训练数据编造任何景点名称、地址或描述。所有景点数据必须来源于 `maps_text_search` 工具。
2. **搜索触发机制**: 只要用户的请求涉及景点查询、兴趣点搜索或地理位置信息，你必须第一时间调用工具。
3. **多维搜索策略**: 如果用户的偏好包含多个维度，你应该针对性地提取关键词进行多次调用或组合关键词搜索。

**重要格式要求**:
你必须在回复的最后，将所有搜集到的景点信息整理成一个标准的 JSON 数组格式。
"""

WEATHER_AGENT_PROMPT = """你是天气查询专家。你的任务是利用专业的地理信息工具，获取目标城市最实时的天气状况及预报信息。

**核心准则:**
1. **绝对工具依赖**: 所有天气数据必须完全来源于 `maps_weather` 工具的实时返回。
2. **零容忍幻觉**: 如果工具未返回特定日期或城市的天气数据，你必须如实报告"无法获取"。

**最终目标:**
你必须为行程规划器提供详尽的气象背景，包含：日期、天气现象、温度、风力和风向。
"""

HOTEL_AGENT_PROMPT = """你是酒店推荐专家。任务：根据城市和景点，所有的酒店数据必须来自 `maps_text_search` 工具。

**核心指令:**
1. **工具先行**: 严禁凭记忆编造数据。收到需求后必须立即调用工具。
2. **关键词构造**: 根据用户偏好灵活调整 `keywords` 参数。

**数据提取规范:**
必须记录并输出：名称、精确地址、经纬度坐标、价格区间及评分。
"""

PLANNER_AGENT_PROMPT = """你是行程规划专家。你的任务是根据景点信息和天气信息,生成详细的旅行计划。

请严格按照以下JSON格式返回旅行计划:
```json
{{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {{
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {{...}},
      "attractions": [...],
      "meals": [...]
    }}
  ],
  "weather_info": [...],
  "overall_suggestions": "总体建议",
  "budget": {{...}}
}}
```

**重要提示:**
1. weather_info数组必须包含每一天的天气信息
2. 温度必须是纯数字(不要带°C等单位)
3. 每天安排2-3个景点
4. 考虑景点之间的距离和游览时间
5. 每天必须包含早中晚三餐
"""

INTENT_PARSER_PROMPT = """你是用户意图解析专家。分析用户对旅行计划的反馈，提取调整意图。

**输入**:
- 当前行程摘要
- 用户反馈文本

**输出格式** (仅输出JSON，不要其他文字):
```json
{{
  "intent": "modify_attractions | modify_hotels | modify_schedule | confirm | other",
  "target_days": [0, 1, ...],  // 目标天数列表，从0开始
  "action": "add | remove | replace | adjust_time | change_location",
  "details": "具体调整内容描述",
  "reasoning": "简短的推理过程"
}}
```

**意图分类说明**:
- modify_attractions: 调整景点（增加/减少/替换景点）
- modify_hotels: 调整酒店（换酒店、调整位置）
- modify_schedule: 调整日程安排（时间安排、行程节奏）
- confirm: 用户确认满意
- other: 其他需求或不明确

**示例**:
用户反馈: "第一天景点有点多，第二天空闲时间多一些"
输出: {"intent": "modify_attractions", "target_days": [0, 1], "action": "adjust_time", "details": "第一天减少景点，第二天增加景点", "reasoning": "用户希望平衡两天的行程密度"}
"""

ADJUSTMENT_PROMPT = """你是行程调整专家。根据用户意图调整现有行程。

**当前行程**:
{current_plan}

**用户意图**:
- 意图类型: {intent}
- 目标天数: {target_days}
- 操作类型: {action}
- 详细说明: {details}

**调整原则**:
1. 保持其他天数的行程不变，只调整用户指定的天数
2. 如果是减少景点，优先移除评分较低或距离较远的景点
3. 如果是增加景点，从备选景点中选择
4. 调整后确保行程合理（时间、距离、预算）
5. 必须输出完整的 TripPlan JSON 格式

**输出要求**:
输出调整后的完整行程 JSON，格式与原行程相同。
"""


# ===================== 状态定义 =====================

class ChatAgentState(TypedDict):
    """多轮对话状态 - 支持持续性互"""

    # 用户输入信息
    city: str
    start_date: str
    end_date: str
    interests: List[str]
    accommodation_type: Optional[str]
    budget_per_day: Optional[int]
    transportation_mode: Optional[str]

    # 中间结果
    attractions_data: Annotated[List[Dict[str, Any]], operator.add]
    weather_data: Annotated[List[Dict[str, Any]], operator.add]
    hotels_data: Annotated[List[Dict[str, Any]], operator.add]

    # 对话相关（新增）
    messages: Annotated[List[Dict[str, str]], operator.add]  # 对话历史
    user_feedback: Optional[str]      # 用户最新反馈
    intent: Optional[str]             # 解析出的意图
    target_days: Optional[List[int]]  # 目标天数
    action: Optional[str]             # 操作类型
    details: Optional[str]            # 详细说明

    # 流程控制（新增）
    iteration_count: int              # 迭代次数
    is_satisfied: bool                # 用户是否满意

    # 最终结果
    final_plan: Optional[Dict[str, Any]]
    context: Annotated[List[str], operator.add]
    execution_errors: Annotated[List[str], operator.add]


# ===================== 多轮对话系统 =====================

class TripChatSystem:
    """支持多轮对话的旅行规划系统"""

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
            print(f"✅ 成功加载工具: {tool_names}")

            # 构建图
            self.graph = self._create_chat_graph()

        except Exception as e:
            print(f"❌ MCP 初始化失败: {str(e)}")
            raise

    def _create_agent_node(self, system_prompt: str, name: str, prepare_input_fn, output_state_key: str):
        """创建工具调用 Agent 节点"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        executor = AgentExecutor(agent=agent, tools=self.tools, verbose=settings.debug)

        async def node(state: ChatAgentState):
            try:
                input_str = prepare_input_fn(state)
                print(f"\n[{name}] 正在处理...")

                result = await executor.ainvoke({"input": input_str})
                output_text = result.get('output', '')

                import json
                import re

                structured_data = []
                json_pattern = r'(\[[\s\S]*?\]|\{[\s\S]*?\})'
                matches = re.findall(json_pattern, output_text)

                for match_str in matches:
                    try:
                        raw_json = json.loads(match_str)
                        if isinstance(raw_json, list):
                            structured_data.extend(raw_json)
                        elif isinstance(raw_json, dict):
                            list_keys = ['hotels', 'pois', 'attractions', 'weather', 'forecasts']
                            found_list = False
                            for k in list_keys:
                                if k in raw_json and isinstance(raw_json[k], list):
                                    structured_data.extend(raw_json[k])
                                    found_list = True
                                    break
                            if not found_list:
                                structured_data.append(raw_json)
                    except json.JSONDecodeError:
                        continue

                print(f"✅ {name} 提取 {len(structured_data)} 条数据")
                return {output_state_key: structured_data}

            except Exception as e:
                print(f"❌ {name} 错误: {str(e)}")
                return {output_state_key: [], "execution_errors": [f"{name}: {str(e)}"]}

        return node

    async def _parse_intent_node(self, state: ChatAgentState):
        """解析用户反馈意图"""
        try:
            user_feedback = state.get('user_feedback', '')
            current_plan = state.get('final_plan')

            if not user_feedback:
                return {"intent": "other", "details": "无用户反馈"}

            # 构建行程摘要
            plan_summary = self._summarize_plan(current_plan) if current_plan else "暂无行程"

            prompt = ChatPromptTemplate.from_messages([
                ("system", INTENT_PARSER_PROMPT),
                ("user", "当前行程摘要:\n{plan_summary}\n\n用户反馈:\n{feedback}")
            ])

            chain = prompt | self.llm

            response = await chain.ainvoke({
                "plan_summary": plan_summary,
                "feedback": user_feedback
            })

            # 解析响应
            import json
            import re

            content = response.content
            json_match = re.search(r'\{[\s\S]*\}', content)

            if json_match:
                intent_data = json.loads(json_match.group())
                print(f"📝 解析意图: {intent_data.get('intent')} - {intent_data.get('details')}")

                return {
                    "intent": intent_data.get('intent', 'other'),
                    "target_days": intent_data.get('target_days', []),
                    "action": intent_data.get('action'),
                    "details": intent_data.get('details'),
                    "messages": [{"role": "user", "content": user_feedback}]
                }

            return {"intent": "other", "details": "无法解析"}

        except Exception as e:
            print(f"❌ 意图解析错误: {str(e)}")
            return {"intent": "other", "details": str(e)}

    async def _adjust_plan_node(self, state: ChatAgentState):
        """根据意图调整行程"""
        try:
            current_plan = state.get('final_plan')
            intent = state.get('intent')
            target_days = state.get('target_days', [])
            action = state.get('action')
            details = state.get('details')

            if not current_plan:
                print("⚠️ 无当前行程，无法调整")
                return {}

            print(f"🔧 调整行程: {intent} - {details}")

            import json
            plan_json = json.dumps(current_plan, ensure_ascii=False, indent=2)

            prompt = ChatPromptTemplate.from_messages([
                ("system", ADJUSTMENT_PROMPT),
                ("user", "请调整行程")
            ])

            chain = prompt | self.llm.with_structured_output(TripPlan, method="json_mode")

            response = await chain.ainvoke({
                "current_plan": plan_json,
                "intent": intent,
                "target_days": str(target_days),
                "action": action or "adjust_time",
                "details": details or "用户要求调整"
            })

            print("✅ 行程调整完成")
            return {
                "final_plan": response.model_dump(),
                "iteration_count": state.get('iteration_count', 0) + 1,
                "messages": [{"role": "assistant", "content": f"已根据您的反馈调整行程: {details}"}]
            }

        except Exception as e:
            print(f"❌ 行程调整错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"execution_errors": [f"调整失败: {str(e)}"]}

    async def _plan_trip_node(self, state: ChatAgentState):
        """生成初始行程规划"""
        try:
            print("\n📋 正在规划行程...")

            start = datetime.strptime(state['start_date'], '%Y-%m-%d')
            end = datetime.strptime(state['end_date'], '%Y-%m-%d')
            trip_days = (end - start).days + 1

            attractions = state.get('attractions_data', [])
            weather_info = state.get('weather_data', [])
            hotels = state.get('hotels_data', [])

            print(f"   景点: {len(attractions)} 条, 天气: {len(weather_info)} 条, 酒店: {len(hotels)} 条")

            planner_prompt = ChatPromptTemplate.from_messages([
                ("system", PLANNER_AGENT_PROMPT),
                ("user", "{context}")
            ])

            planner_chain = planner_prompt | self.llm.with_structured_output(TripPlan, method="json_mode")

            attractions_summary = self._format_attractions(attractions)
            weather_summary = self._format_weather(weather_info)
            hotels_summary = self._format_hotels(hotels)

            res = await planner_chain.ainvoke({
                "context": f"""
根据以下信息为用户生成详细的旅行计划：

📍 用户需求：
- 城市: {state['city']}
- 日期: {state['start_date']} 至 {state['end_date']} ({trip_days}天)
- 兴趣: {', '.join(state['interests'])}
- 住宿: {state.get('accommodation_type') or '未指定'}
- 预算: {state.get('budget_per_day') or '未指定'}元/天

【景点信息】
{attractions_summary}

【天气预报】
{weather_summary}

【酒店选项】
{hotels_summary}

请生成完整的 {trip_days} 天行程计划。
"""
            })

            print("✅ 行程规划完成")
            return {
                "final_plan": res.model_dump(),
                "messages": [{"role": "assistant", "content": "行程规划已完成，请查看并提出您的反馈。"}]
            }

        except Exception as e:
            print(f"❌ 规划错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"execution_errors": [f"规划失败: {str(e)}"]}

    def _summarize_plan(self, plan: Optional[Dict[str, Any]]) -> str:
        """生成行程摘要"""
        if not plan:
            return "暂无行程"

        lines = []
        for day in plan.get('days', []):
            day_idx = day.get('day_index', 0) + 1
            attractions = day.get('attractions', [])
            attr_names = [a.get('name', '未知') for a in attractions]
            lines.append(f"第{day_idx}天: {', '.join(attr_names) if attr_names else '暂无景点'}")

        return "\n".join(lines)

    def _format_attractions(self, attractions: List[Dict[str, Any]]) -> str:
        if not attractions:
            return "暂无景点信息"
        lines = []
        for i, attr in enumerate(attractions[:10], 1):
            name = attr.get('name', '未知')
            desc = attr.get('description', '')[:50]
            lines.append(f"{i}. {name} - {desc}...")
        return "\n".join(lines)

    def _format_weather(self, weather: List[Dict[str, Any]]) -> str:
        if not weather:
            return "暂无天气信息"
        lines = []
        for w in weather[:7]:
            date = w.get('date', '未知')
            day_w = w.get('day_weather', '晴')
            temp = w.get('day_temp', '--')
            lines.append(f"{date}: {day_w}, {temp}℃")
        return "\n".join(lines)

    def _format_hotels(self, hotels: List[Dict[str, Any]]) -> str:
        if not hotels:
            return "暂无酒店信息"
        lines = []
        for i, hotel in enumerate(hotels[:5], 1):
            name = hotel.get('name', '未知')
            lines.append(f"{i}. {name}")
        return "\n".join(lines)

    def _create_chat_graph(self):
        """创建多轮对话图"""
        workflow = StateGraph(ChatAgentState)

        # 数据收集节点
        workflow.add_node(
            "attraction_expert",
            self._create_agent_node(
                ATTRACTION_AGENT_PROMPT,
                "景点专家",
                lambda s: f"城市: {s['city']}, 兴趣: {s['interests']}。返回 JSON 数组格式的景点信息。",
                "attractions_data"
            )
        )

        workflow.add_node(
            "weather_expert",
            self._create_agent_node(
                WEATHER_AGENT_PROMPT,
                "天气专家",
                lambda s: f"查询 {s['city']} 从 {s['start_date']} 到 {s['end_date']} 的天气。",
                "weather_data"
            )
        )

        workflow.add_node(
            "hotel_expert",
            self._create_agent_node(
                HOTEL_AGENT_PROMPT,
                "酒店专家",
                lambda s: f"在 {s['city']} 找酒店，类型: {s.get('accommodation_type', '中档')}。",
                "hotels_data"
            )
        )

        # 规划节点
        workflow.add_node("plan_trip", self._plan_trip_node)

        # 构建流程
        workflow.set_entry_point("attraction_expert")
        workflow.add_edge("attraction_expert", "weather_expert")
        workflow.add_edge("weather_expert", "hotel_expert")
        workflow.add_edge("hotel_expert", "plan_trip")
        workflow.add_edge("plan_trip", END)

        return workflow.compile(checkpointer=self.checkpointer)


# ===================== 会话管理 =====================

class TripChatSession:
    """多轮对话会话管理"""

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

    async def start(self, request: TripRequest) -> Dict[str, Any]:
        """开始规划行程"""
        await self.initialize()

        inputs = {
            "city": request.city,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "interests": request.interests,
            "accommodation_type": request.accommodation_type,
            "budget_per_day": request.budget_per_day,
            "transportation_mode": request.transportation_mode,
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "messages": [],
            "user_feedback": None,
            "intent": None,
            "target_days": None,
            "action": None,
            "details": None,
            "iteration_count": 0,
            "is_satisfied": False,
            "final_plan": None,
            "context": [],
            "execution_errors": [],
        }

        # 执行到规划完成后暂停
        result = await self.system.graph.ainvoke(inputs, self.config)
        return result.get('final_plan')

    async def feedback(self, user_input: str) -> Dict[str, Any]:
        """提交用户反馈，继续对话"""
        # 获取当前状态
        current_state = await self.system.graph.aget_state(self.config)
        current_plan = current_state.values.get('final_plan')

        # 如果用户确认满意
        if user_input.strip() in ['确认', '满意', '好的', '可以', '没问题', 'confirm']:
            return current_plan

        if not current_plan:
            print("⚠️ 暂无行程，无法调整")
            return None

        # 1. 解析用户意图
        print("📝 解析您的反馈...")
        intent_state = {
            "user_feedback": user_input,
            "final_plan": current_plan
        }

        intent_result = await self.system._parse_intent_node(intent_state)
        intent = intent_result.get('intent')

        # 2. 根据意图处理
        if intent == 'confirm':
            print("✅ 您对行程满意！")
            return current_plan

        if intent not in ['modify_attractions', 'modify_hotels', 'modify_schedule']:
            print("⚠️ 暂时无法理解您的需求，请换种方式表达")
            return current_plan

        # 3. 执行调整
        adjust_state = {
            "final_plan": current_plan,
            "intent": intent,
            "target_days": intent_result.get('target_days', []),
            "action": intent_result.get('action'),
            "details": intent_result.get('details'),
            "iteration_count": current_state.values.get('iteration_count', 0) + 1
        }

        adjust_result = await self.system._adjust_plan_node(adjust_state)
        new_plan = adjust_result.get('final_plan')

        if new_plan:
            # 更新图状态
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
    print("🗺️  智能旅行规划助手 - 多轮对话版")
    print("=" * 60)

    session = TripChatSession()

    try:
        # 获取用户输入
        print("\n请输入您的旅行需求：")
        city = input("城市: ").strip() or "北京"
        start_date = input("开始日期 (YYYY-MM-DD): ").strip() or "2026-03-25"
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

        print(f"\n🚀 正在为您规划 {city} 的行程...\n")

        # 开始规划
        plan = await session.start(request)

        if not plan:
            print("❌ 规划失败，请重试")
            return

        # 显示行程
        print("=" * 60)
        print("📋 您的行程计划：")
        print("=" * 60)
        print(session.format_plan(plan))

        # 多轮对话循环
        print("\n" + "=" * 60)
        print("💬 您可以提出修改意见，例如：")
        print("   - 第一天景点有点多")
        print("   - 酒店换个离景点近的")
        print("   - 第二天时间太紧了")
        print("   输入 '确认' 或 '满意' 完成规划")
        print("=" * 60)

        while True:
            user_input = input("\n您的反馈: ").strip()

            if not user_input:
                continue

            if user_input in ['确认', '满意', '好的', '可以', '没问题', 'confirm', 'exit', 'quit', 'q']:
                print("\n✅ 行程规划完成！祝您旅途愉快！")
                break

            # 提交反馈
            print("\n🔄 正在调整行程...")
            plan = await session.feedback(user_input)

            if plan:
                print("\n" + "=" * 60)
                print("📋 调整后的行程：")
                print("=" * 60)
                print(session.format_plan(plan))
            else:
                print("⚠️ 调整失败，请重试")

    except KeyboardInterrupt:
        print("\n\n👋 已取消")
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(interactive_main())