import asyncio
import os
import operator
import sys
from pathlib import Path
from typing import Annotated, List, TypedDict, Dict, Any, Optional  # ✅ 添加 Optional

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
# LangChain 1.0+ 中，Agent 相关 API 已移到 langchain_classic
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# 假设你的目录结构保持不变
sys.path.insert(0, str(Path(__file__).parent.parent))
from model.schemas import TripPlan, TripRequest ,Attraction, WeatherInfo, Hotel  # ✅ 添加 DayPlan

# ===================== Prompt 定义（必须在类之前）=====================
ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。你的任务是根据指定的城市和用户偏好，利用专业搜索工具获取真实、准确的景点信息。

**核心准则 (Core Principles):**
1. **工具依赖性**: 你严禁基于自身的训练数据编造任何景点名称、地址或描述。所有景点数据必须来源于 `maps_text_search` 工具。
2. **搜索触发机制**: 只要用户的请求涉及景点查询、兴趣点搜索或地理位置信息，你必须第一时间调用工具。严禁在调用工具前向用户提供任何假设性的建议。
3. **多维搜索策略**: 如果用户的偏好包含多个维度（例如：既要“历史”又要“自然风景”），你应该针对性地提取关键词进行多次调用或组合关键词搜索。

**工具调用策略 (Tool Strategy):**
你所使用的 `maps_text_search` 工具接受两个关键参数：
- `keywords`: 必须从用户意图中提取最具代表性的“景点类型”或“地理特征”作为关键词。
- `city`: 必须准确识别用户提到的目标城市名。

**操作规范 (Operational Constraints):**
- **严禁虚假确认**: 在工具返回结果之前，不要对用户说“好的，我为您找到了以下景点”。
- **参数完整性**: 确保传入工具的 `city` 参数不包含行政区划后缀（例如：使用“北京”而非“北京市”），除非用户明确指定了某个区。
- **负面约束**: 如果工具未能返回相关结果，请如实告知，不要自行脑补相似景点。

**交互示例 (For Internal Reasoning):**
- 用户: "我想去北京看一些历史古迹。"
- 你的逻辑: 提取 `keywords="历史古迹"`, `city="北京"` -> 发起原生工具调用请求。
- 用户: "上海有什么适合散步的公园？"
- 你的逻辑: 提取 `keywords="公园"`, `city="上海"` -> 发起原生工具调用请求。

**最终目标:**
你的输出应当基于工具返回的原始数据进行整合，为用户提供包括名称、精确地址、经纬度和景点描述的结构化信息。
"""

WEATHER_AGENT_PROMPT = """你是天气查询专家。你的任务是利用专业的地理信息工具，获取目标城市最实时的天气状况及预报信息。

**核心准则 (Core Principles):**
1. **绝对工具依赖**: 你严禁根据历史记忆或常识推测天气。所有天气数据（包括温度、湿度、风向、天气现象）必须完全来源于 `amap_maps_weather` 工具的实时返回。
2. **零容忍幻觉**: 如果工具未返回特定日期或城市的天气数据，你必须如实报告“无法获取”，严禁通过周边城市数据进行自行推导。
3. **任务优先级**: 在收到查询指令时，你的首要动作是发起工具调用。在工具返回结果前，禁止提供任何关于天气的描述性文字。

**工具调用策略 (Tool Strategy):**
你所使用的 `maps_weather` 工具具有以下操作规范：
- `city`: 必须从用户请求中精准提取城市名称。
- **行政区划处理**: 优先提取标准城市名（如“北京”、“杭州”）。如果用户提到了具体的区（如“朝阳区”），请确保参数的准确性。

**操作规范 (Operational Constraints):**
- **多维度信息提取**: 在获得工具反馈后，你不仅需要关注“天气现象”（晴/雨），还必须详细记录“温度”、“风力”和“风向”，这些数据对于后续的行程规划至关重要。
- **时效性校验**: 始终检查返回数据是否覆盖了用户要求的旅行日期。
- **无干扰回复**: 你的内部思考过程应聚焦于“城市参数是否识别正确”，一旦识别完成，立即触发工具。

**交互示例 (Internal Logic):**
- 用户: "帮我看看下周三北京冷不冷。"
- 你的逻辑: 识别目标城市为 `city="北京"` -> 发起原生 `maps_weather` 调用。
- 用户: "成都现在下雨吗？"
- 你的逻辑: 识别目标城市为 `city="成都"` -> 发起原生 `maps_weather` 调用。

**最终目标:**
你必须为行程规划器（Planner）提供详尽的气象背景。你的输出应包含：实时天气、最高/最低气温、以及任何可能影响出行的气象预警或建议。
"""

HOTEL_AGENT_PROMPT = """你是酒店推荐专家。任务：根据城市和景点，所有的酒店数据必须来自 `maps_text_search` 工具，以获取真实住宿信息。

**核心指令 (Strict Constraints):**
1. **工具先行**: 严禁凭记忆编造数据。收到需求后必须立即调用工具，在获取结果前禁止提供任何推荐或承诺。
2. **关键词构造**: 根据用户偏好灵活调整 `keywords` 参数：
   - 默认：使用“酒店”或“宾馆”。
   - 档次：用户要求“五星级/高档”时，设为“豪华酒店”或“五星级酒店”。
   - 位置：用户提及特定景点时，设为“景点名称附近酒店”。
3. **地理关联**: 优先推荐靠近用户兴趣景点或核心商圈的酒店。

**数据提取规范:**
- 必须记录并输出：名称、精确地址、经纬度坐标（必填，用于行程规划）、价格区间及评分。
- 严禁废话：识别需求后直接触发工具调用，无需寒暄。

**交互示例:**
- 用户：“北京故宫附近五星级” -> 逻辑：`city="北京"`, `keywords="故宫附近豪华酒店"` -> 工具调用。
- 用户：“上海快捷酒店” -> 逻辑：`city="上海"`, `keywords="快捷酒店"` -> 工具调用。

**目标**: 为 Planner 提供包含精确坐标和特征的结构化酒店列表，确保其能计算交通距离。
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
      "hotel": {{
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {{"longitude": 116.397128, "latitude": 39.916527}},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      }},
      "attractions": [
        {{
          "name": "景点名称",
          "address": "详细地址",
          "location": {{"longitude": 116.397128, "latitude": 39.916527}},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }}
      ],
      "meals": [
        {{"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30}},
        {{"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50}},
        {{"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}}
      ]
    }}
  ],
  "weather_info": [
    {{
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级"
    }}
  ],
  "overall_suggestions": "总体建议",
  "budget": {{
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }}
}}
```

**重要提示:**
1. weather_info数组必须包含每一天的天气信息
2. 温度必须是纯数字(不要带°C等单位)
3. 每天安排2-3个景点
4. 考虑景点之间的距离和游览时间
5. 每天必须包含早中晚三餐
6. 提供实用的旅行建议
7. **必须包含预算信息**:
   - 景点门票价格(ticket_price)
   - 餐饮预估费用(estimated_cost)
   - 酒店预估费用(estimated_cost)
   - 预算汇总(budget)包含各项总费用
"""


# ===================== 1. 状态定义 =====================
class AgentState(TypedDict):
    """多智能体状态 - 完整的数据流转架构"""
    # 用户输入信息
    city: str
    start_date: str
    end_date: str
    interests: List[str]
    accommodation_type: Optional[str]
    budget_per_day: Optional[int]
    transportation_mode: Optional[str]
    
    # 中间结果：各Agent的结构化输出
    attractions_data: Annotated[List[Dict[str, Any]], operator.add]  
    weather_data: Annotated[List[Dict[str, Any]], operator.add]      
    hotels_data: Annotated[List[Dict[str, Any]], operator.add]

    # 执行日志
    context: Annotated[List[str], operator.add]
    
    # 最终结果
    final_plan: Optional[TripPlan]
    execution_errors: Annotated[List[str], operator.add]  # 执行错误记录

# ===================== 2. 重写 TripGraphSystem =====================
class TripGraphSystem:
    def __init__(self, api_key: str, amap_key: str):
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model='deepseek-chat', 
            api_key=api_key, 
            base_url='https://api.deepseek.com'
        )
        self.amap_key = amap_key
        self.client = None
        self.tools = None

    async def initialize(self):
        """使用 MultiServerMCPClient 初始化工具"""
        # ✅ 添加: 验证 API Key
        if not self.amap_key:
            raise ValueError("❌ AMAP_MAPS_API_KEY 未设置")
        
        # 配置多个 MCP 服务器
        server_config = {
            "amap": {
                "command": "uvx",
                "args": ["amap-mcp-server"],
                "transport": "stdio",
                # 在这里注入环境变量，彻底解决报错问题
                "env": {
                    **os.environ, 
                    "AMAP_MAPS_API_KEY": self.amap_key
                }
            }
        }
        
        try:
            # 1. 创建多服务客户端
            self.client = MultiServerMCPClient(server_config)
            
            # 2. 直接获取适配好的 LangChain 工具列表
            # 该方法内部会自动处理 Session 的建立和初始化
            self.tools = await self.client.get_tools()
            
            # ✅ 添加: 验证工具列表
            if not self.tools:
                raise ValueError("❌ 未能加载任何工具")
            
            tool_names = [t.name for t in self.tools]
            print(f"✅ 成功加载工具: {tool_names}")
            
            # ✅ 添加: 验证必需工具
            required_tools = {'maps_text_search', 'maps_weather'}
            available_tools = set(tool_names)
            missing = required_tools - available_tools
            if missing:
                print(f"⚠️ 缺少工具: {missing}")
                
        except Exception as e:
            print(f"❌ MCP 初始化失败: {str(e)}")
            raise

    def _create_agent_node(self, system_prompt: str, name: str, prepare_input_fn, output_state_key: str):
        """
        创建一个 Agent 节点
        
        Args:
            system_prompt: 系统提示词（详细的操作规范）
            name: Agent 名称（用于日志）
            prepare_input_fn: 根据状态准备输入的函数
            output_state_key: 输出结果存储的状态键（如 'attractions_data', 'weather_data', 'hotels_data'）
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 使用 LangChain 1.0+ 的最新 API
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)
        
        async def node(state: AgentState):
            try:
                input_str = prepare_input_fn(state)
                print(f"\n[Node: {name}] 正在处理请求...")
                
                result = await executor.ainvoke({"input": input_str})
                output_text = result.get('output', '')
                
                import json
                import re
                
                structured_data = []
                
                # 1. 改为非贪婪匹配模式，并使用 re.findall 寻找所有 JSON 块
                # pattern 支持匹配 {} 或 []
                json_pattern = r'(\[[\s\S]*?\]|\{[\s\S]*?\})'
                matches = re.findall(json_pattern, output_text)

                for match_str in matches:
                    try:
                        raw_json = json.loads(match_str)
                        
                        # 2. 依然保留原有的“打平”逻辑，但改为 extend 到结果列表
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
                        continue # 某一块解析失败则跳过，继续解析下一块

                # 3. 结果反馈
                count = len(structured_data)
                print(f"✅ {name} 成功提取 {count} 条条目")
                        
                return {
                    output_state_key: structured_data,
                    "context": [f"### {name} 汇报\n- 收集到 {count} 条数据\n"],
                }
                
            except Exception as e:
                error_msg = f"❌ {name} 节点崩溃: {str(e)}"
                print(error_msg)
                return {
                    output_state_key: [],
                    "context": [error_msg],
                    "execution_errors": [error_msg],
                }
        
        return node

    def create_graph(self):
        workflow = StateGraph(AgentState)

        # 添加节点 - 使用详细的 Prompts 和具体的输入生成函数
        
        # 景点专家节点
        workflow.add_node(
            "attraction_expert",
            self._create_agent_node(
                ATTRACTION_AGENT_PROMPT,
                "景点专家",
                lambda state: f"你需要为城市：{state['city']} 寻找真实的景点信息。用户兴趣是：{', '.join(state['interests'])}。请务必使用 maps_text_search 工具获取最新数据，严禁凭记忆回答,请返回 JSON 格式的景点列表。",
                "attractions_data"  # 指定输出键
            )
        )
        
        # 天气专家节点
        workflow.add_node(
            "weather_expert",
            self._create_agent_node(
                WEATHER_AGENT_PROMPT,
                "天气专家",
                lambda state: f"查询 {state['city']} 从 {state['start_date']} 到 {state['end_date']} 的天气情况。请务必使用 maps_weather 工具获取最新数据，严禁凭记忆回答，请返回 JSON 格式的天气信息列表。",
                "weather_data"  # 指定输出键
            )
        )
        
        # 酒店专家节点
        workflow.add_node(
            "hotel_expert",
            self._create_agent_node(
                HOTEL_AGENT_PROMPT,
                "酒店专家",
                lambda state: f"在 {state['city']} 寻找酒店。参考位置：{state['attractions_data'][0]['name'] if state['attractions_data'] else state['city']} 附近。要求类型：{state.get('accommodation_type', '中档')}。严禁凭记忆回答，请返回 JSON 格式的酒店信息列表。",
                "hotels_data"  # 指定输出键
            )
        )
        
        # 规划者节点：整合所有数据生成结构化 JSON
        async def planner_node(state: AgentState):
            try:
                print("\n📋 规划专家正在整合行程...")
                
                # ✅ 计算旅程天数
                from datetime import datetime
                start = datetime.strptime(state['start_date'], '%Y-%m-%d')
                end = datetime.strptime(state['end_date'], '%Y-%m-%d')
                trip_days = (end - start).days + 1
                
                # ✅ 验证中间数据
                attractions = state.get('attractions_data', [])
                weather_info = state.get('weather_data', [])
                hotels = state.get('hotels_data', [])
                
                print("📊 数据收集汇总:")
                print(f"   - 景点: {len(attractions)} 条")
                print(f"   - 天气: {len(weather_info)} 条")
                print(f"   - 酒店: {len(hotels)} 条")
                
                # ✅ 数据验证和错误检查
                validation_errors = []
                if len(attractions) == 0:
                    validation_errors.append("⚠️ 景点数据为空")
                if len(weather_info) == 0:
                    validation_errors.append("⚠️ 天气数据为空")
                if len(hotels) == 0:
                    validation_errors.append("⚠️ 酒店数据为空")
                
                if validation_errors:
                    print("\n".join(validation_errors))
                
                # 构建规划 Prompt
                planner_prompt = ChatPromptTemplate.from_messages([
                    ("system", PLANNER_AGENT_PROMPT),
                    ("user", "{context}")
                ])
                
                # 使用结构化输出
                planner_chain = planner_prompt | self.llm.with_structured_output(TripPlan,method="json_mode")
                
                # 将收集到的结构化数据转换为文本描述
                attractions_summary = self._format_attractions(attractions)
                weather_summary = self._format_weather(weather_info)
                hotels_summary = self._format_hotels(hotels)
                
                # 调用规划者 - 使用结构化数据而不是混杂文本
                res = await planner_chain.ainvoke({
                    "context": f"""
根据以下信息为用户生成详细的旅行计划：

📍 用户需求：
- 城市: {state['city']}
- 开始日期: {state['start_date']}
- 结束日期: {state['end_date']}
- 旅程天数: {trip_days} 天
- 兴趣: {', '.join(state['interests'])}
- 住宿: {state.get('accommodation_type') or '未指定'}
- 交通: {state.get('transportation_mode') or '未指定'}
- 预算: {state.get('budget_per_day') or '未指定'}元/天

🎯 收集到的信息：

【景点信息】
{attractions_summary}

【天气预报】
{weather_summary}

【酒店选项】
{hotels_summary}

请生成 {trip_days} 天的完整行程计划，从 {state['start_date']} 到 {state['end_date']}。
每一天都必须有对应的 DayPlan 对象。
请按照指定的 JSON 格式生成完整的行程计划。
记住：
1. 每天的天气信息必须对应正确的日期
2. 每个景点必须包含具体的地址、坐标和门票价格
3. 酒店必须贴近景点分布
4. 必须包含预算汇总信息
"""
                })
                
                # ✅ 添加输出验证
                if not isinstance(res, TripPlan):
                    raise ValueError(f"❌ 规划输出类型错误: {type(res)}")
                
                actual_days = len(res.days)
                if actual_days != trip_days:
                    print(f"⚠️ 天数不匹配: 预期 {trip_days} 天，实际 {actual_days} 天")
                
                if len(res.weather_info) == 0:
                    print(f"⚠️ 缺少天气信息，预期 {trip_days} 天的天气数据")
                
                if res.budget is None:
                    print("⚠️ 缺少预算信息")
                
                print("✅ 规划专家已生成行程")
                return {
                    "final_plan": res.model_dump(),  # 转换为字典便于序列化
                    "context": ["✅ 规划完成"],
                }
            except Exception as e:
                error_msg = f"❌ 规划专家执行出错: {str(e)}"
                print(error_msg)
                import traceback
                traceback.print_exc()
                return {
                    "final_plan": None,
                    "context": [error_msg],
                    "execution_errors": [error_msg],
                }
        
        workflow.add_node("planner", planner_node)

        # 连线 - 按顺序执行：景点 → 天气 → 酒店 → 规划者
        workflow.set_entry_point("attraction_expert")
        workflow.add_edge("attraction_expert", "weather_expert")
        workflow.add_edge("weather_expert", "hotel_expert")
        workflow.add_edge("hotel_expert", "planner")
        workflow.add_edge("planner", END)

        return workflow.compile()
    
    def _format_attractions(self, attractions: List[Dict[str, Any]]) -> str:
        """格式化景点数据为文本"""
        if not attractions:
            return "暂无景点信息"
        
        lines = []
        for i, attr in enumerate(attractions[:10], 1):  # 最多显示10个
            name = attr.get('name', '未知')
            desc = attr.get('description', '')[:50]
            price = attr.get('ticket_price', 0)
            duration = attr.get('visit_duration', 60)
            lines.append(f"{i}. {name} - 门票¥{price} - 游览{duration}分钟 - {desc}...")
        
        return "\n".join(lines)
    
    def _format_weather(self, weather: List[Dict[str, Any]]) -> str:
        """格式化天气数据为文本"""
        if not weather:
            return "暂无天气信息"
        
        lines = []
        for w in weather[:7]:  # 最多显示7天
            date = w.get('date', '未知日期')
            day_w = w.get('day_weather', '晴')
            temp = w.get('day_temp', '--')
            lines.append(f"{date}: {day_w}, 白天温度{temp}℃")
        
        return "\n".join(lines)
    
    def _format_hotels(self, hotels: List[Dict[str, Any]]) -> str:
        """格式化酒店数据为文本"""
        if not hotels:
            return "暂无酒店信息"
        
        lines = []
        for i, hotel in enumerate(hotels[:5], 1):  # 最多显示5个
            name = hotel.get('name', '未知')
            type_ = hotel.get('type', '')
            price = hotel.get('estimated_cost', 0)
            lines.append(f"{i}. {name} ({type_}) - 预估¥{price}/晚")
        
        return "\n".join(lines)

# ===================== 3. 运行逻辑 =====================
async def main():
    # 参数配置
    DEEPSEEK_KEY = "sk-5c6052d783934e59a0a3a73066a3cdcd"
    AMAP_KEY = "0ed6e5ef8effdc096432cd039075c0fc"

    print("🚀 启动 TripGraphSystem...")

    system = TripGraphSystem(DEEPSEEK_KEY, AMAP_KEY)
    
    # 初始化 MCP 客户端
    await system.initialize()
    
    try:
        # 构建图
        app = system.create_graph()
        
        # ✅ 第一步：使用 TripRequest 模型验证输入数据
        trip_request = TripRequest(
            city="北京",
            start_date="2026-01-30",
            end_date="2026-02-02",              # 3 天行程
            interests=["故宫", "国家博物馆"],
            accommodation_type="五星级",
            budget_per_day=1500,                # 每日预算
            transportation_mode="地铁+出租车"   # 交通方式
        )
        
        # ✅ 第二步：从 TripRequest 转换为 AgentState
        # 这样可以利用 Pydantic 的数据验证和类型检查
        inputs = {
            "city": trip_request.city,
            "start_date": trip_request.start_date,
            "end_date": trip_request.end_date,
            "interests": trip_request.interests,
            "accommodation_type": trip_request.accommodation_type,
            "budget_per_day": trip_request.budget_per_day,
            "transportation_mode": trip_request.transportation_mode,
            # ✅ 初始化中间数据字段
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            # ✅ 初始化日志和错误字段
            "context": [],
            "execution_errors": [],
            "final_plan": None,
        }
        
        print("✅ 已验证输入数据:")
        print(f"   - 城市: {trip_request.city}")
        print(f"   - 日期: {trip_request.start_date} 至 {trip_request.end_date}")
        print(f"   - 兴趣: {', '.join(trip_request.interests)}")
        print(f"   - 住宿: {trip_request.accommodation_type}")
        print(f"   - 预算: {trip_request.budget_per_day}元/天")
        
        # 执行
        print("\n" + "="*50)
        print("🚀 开始规划行程...")
        print("="*50)
        final_state = await app.ainvoke(inputs)
        
        # ✅ 提取最终结果
        final_plan = final_state.get("final_plan")
        execution_errors = final_state.get("execution_errors", [])
        
        print("\n" + "="*50)
        print("--- 最终生成的行程计划 ---")
        print("="*50)
        
        if execution_errors:
            print("\n⚠️ 执行过程中的错误:")
            for err in execution_errors:
                print(f"  {err}")
        
        if final_plan:
            # 美化输出
            import json
            print("\n✅ 行程计划生成成功！")
            print(json.dumps(final_plan, indent=2, ensure_ascii=False))
        else:
            print("\n❌ 未能生成行程计划")
        
        print("="*50)
        
    except ValueError as e:
        print(f"❌ 输入数据验证失败: {str(e)}")
    except Exception as e:
        print(f"❌ 执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # MultiServerMCPClient 不需要手动关闭每一个 session
        # 但在生产环境下，如果 client 有 close 方法可以调用
        pass

if __name__ == "__main__":
    asyncio.run(main())