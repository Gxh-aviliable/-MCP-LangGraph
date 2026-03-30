"""Agent 节点实现

实现各个专家节点和规划节点
"""
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

from backend.agent.state import ChatAgentState
from backend.prompts import (
    ATTRACTION_AGENT_PROMPT,
    WEATHER_AGENT_PROMPT,
    HOTEL_AGENT_PROMPT,
    PLANNER_AGENT_PROMPT,
    INTENT_PARSER_PROMPT,
    ADJUSTMENT_PROMPT,
)
from backend.model import TripPlan
from backend.config.settings import settings


# ===================== 工具函数 =====================

def extract_json_from_text(text: str) -> List[Dict[str, Any]]:
    """从文本中提取 JSON 数据

    Args:
        text: 包含 JSON 的文本

    Returns:
        提取出的数据列表
    """
    structured_data = []
    json_pattern = r'(\[[\s\S]*?\]|\{[\s\S]*?\})'
    matches = re.findall(json_pattern, text)

    for match_str in matches:
        try:
            raw_json = json.loads(match_str)
            if isinstance(raw_json, list):
                structured_data.extend(raw_json)
            elif isinstance(raw_json, dict):
                # 尝试从字典中提取列表字段
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

    return structured_data


def format_attractions(attractions: List[Dict[str, Any]]) -> str:
    """格式化景点信息"""
    if not attractions:
        return "暂无景点信息"
    lines = []
    for i, attr in enumerate(attractions[:10], 1):
        name = attr.get('name', '未知')
        desc = attr.get('description', '')[:50]
        lines.append(f"{i}. {name} - {desc}...")
    return "\n".join(lines)


def format_weather(weather: List[Dict[str, Any]]) -> str:
    """格式化天气信息"""
    if not weather:
        return "暂无天气信息"
    lines = []
    for w in weather[:7]:
        date = w.get('date', '未知')
        day_w = w.get('day_weather', '晴')
        temp = w.get('day_temp', '--')
        lines.append(f"{date}: {day_w}, {temp}℃")
    return "\n".join(lines)


def format_hotels(hotels: List[Dict[str, Any]]) -> str:
    """格式化酒店信息"""
    if not hotels:
        return "暂无酒店信息"
    lines = []
    for i, hotel in enumerate(hotels[:5], 1):
        name = hotel.get('name', '未知')
        lines.append(f"{i}. {name}")
    return "\n".join(lines)


def summarize_plan(plan: Optional[Dict[str, Any]]) -> str:
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


# ===================== 专家节点工厂函数 =====================

def create_expert_node(
    llm,
    tools,
    system_prompt: str,
    node_name: str,
    prepare_input: Callable[[ChatAgentState], str],
    output_key: str
):
    """创建专家节点

    Args:
        llm: 语言模型
        tools: 工具列表
        system_prompt: 系统提示词
        node_name: 节点名称
        prepare_input: 输入准备函数
        output_key: 输出状态键名

    Returns:
        异步节点函数
    """
    # 过滤出该专家需要的特定工具
    tool_name_map = {t.name: t for t in tools}

    # 根据节点类型选择合适的工具
    if "景点" in node_name or "attraction" in output_key:
        # 景点专家只需要 maps_text_search
        filtered_tools = [tool_name_map.get("maps_text_search", tools[0])]
    elif "天气" in node_name or "weather" in output_key:
        # 天气专家只需要 maps_weather
        filtered_tools = [tool_name_map.get("maps_weather", tools[0])]
    elif "酒店" in node_name or "hotel" in output_key:
        # 酒店专家只需要 maps_text_search
        filtered_tools = [tool_name_map.get("maps_text_search", tools[0])]
    else:
        filtered_tools = tools

    print(f"[DEBUG] {node_name} 使用工具: {[t.name for t in filtered_tools]}")

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, filtered_tools, prompt)
    # 强制必须调用工具
    executor = AgentExecutor(
        agent=agent,
        tools=filtered_tools,
        verbose=settings.debug,
        max_iterations=5,  # 限制迭代次数，防止无限循环
        handle_parsing_errors=True  # 处理解析错误
    )

    async def node(state: ChatAgentState) -> Dict[str, Any]:
        try:
            input_str = prepare_input(state)
            print(f"\n[{node_name}] 正在处理...")

            result = await executor.ainvoke({"input": input_str})
            output_text = result.get('output', '')

            structured_data = extract_json_from_text(output_text)
            print(f"[OK] {node_name} 提取 {len(structured_data)} 条数据")

            return {output_key: structured_data}

        except Exception as e:
            print(f"[FAIL] {node_name} 错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return {output_key: [], "execution_errors": [f"{node_name}: {str(e)}"]}

    return node


def create_attraction_node(llm, tools):
    """创建景点专家节点"""
    return create_expert_node(
        llm=llm,
        tools=tools,
        system_prompt=ATTRACTION_AGENT_PROMPT,
        node_name="景点专家",
        prepare_input=lambda s: f"""请搜索 {s['city']} 的景点，用户兴趣: {s['interests']}。

步骤:
1. 调用 maps_text_search 工具搜索景点
2. 将结果整理成 JSON 数组输出

必须调用工具搜索，然后输出 JSON 格式数据。""",
        output_key="attractions_data"
    )


def create_weather_node(llm, tools):
    """创建天气专家节点"""
    return create_expert_node(
        llm=llm,
        tools=tools,
        system_prompt=WEATHER_AGENT_PROMPT,
        node_name="天气专家",
        prepare_input=lambda s: f"""请查询 {s['city']} 从 {s['start_date']} 到 {s['end_date']} 的天气。

步骤:
1. 调用 maps_weather 工具查询天气
2. 将结果整理成 JSON 数组输出

必须调用工具查询，然后输出 JSON 格式数据。""",
        output_key="weather_data"
    )


def create_hotel_node(llm, tools):
    """创建酒店专家节点"""
    return create_expert_node(
        llm=llm,
        tools=tools,
        system_prompt=HOTEL_AGENT_PROMPT,
        node_name="酒店专家",
        prepare_input=lambda s: f"""请搜索 {s['city']} 的酒店，类型: {s.get('accommodation_type', '中档')}。

步骤:
1. 调用 maps_text_search 工具搜索酒店
2. 将结果整理成 JSON 数组输出

必须调用工具搜索，然后输出 JSON 格式数据。""",
        output_key="hotels_data"
    )


# ===================== 规划节点 =====================

async def plan_trip_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """生成初始行程规划"""
    try:
        print("\n[Planner] 正在规划行程...")

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

        planner_chain = planner_prompt | llm.with_structured_output(TripPlan, method="json_mode")

        attractions_summary = format_attractions(attractions)
        weather_summary = format_weather(weather_info)
        hotels_summary = format_hotels(hotels)

        res = await planner_chain.ainvoke({
            "context": f"""
根据以下信息为用户生成详细的旅行计划：

[用户需求]
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

        print("[OK] 行程规划完成")
        return {
            "final_plan": res.model_dump(),
            "messages": [{"role": "assistant", "content": "行程规划已完成，请查看并提出您的反馈。"}]
        }

    except Exception as e:
        print(f"[FAIL] 规划错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"execution_errors": [f"规划失败: {str(e)}"]}


# ===================== 多轮对话节点 =====================

async def parse_intent_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """解析用户反馈意图"""
    try:
        user_feedback = state.get('user_feedback', '')
        current_plan = state.get('final_plan')

        if not user_feedback:
            return {"intent": "other", "details": "无用户反馈"}

        plan_summary = summarize_plan(current_plan) if current_plan else "暂无行程"

        prompt = ChatPromptTemplate.from_messages([
            ("system", INTENT_PARSER_PROMPT),
            ("user", "当前行程摘要:\n{plan_summary}\n\n用户反馈:\n{feedback}")
        ])

        chain = prompt | llm

        response = await chain.ainvoke({
            "plan_summary": plan_summary,
            "feedback": user_feedback
        })

        content = response.content
        json_match = re.search(r'\{[\s\S]*\}', content)

        if json_match:
            intent_data = json.loads(json_match.group())
            print(f"[INFO] 解析意图: {intent_data.get('intent')} - {intent_data.get('details')}")

            return {
                "intent": intent_data.get('intent', 'other'),
                "target_days": intent_data.get('target_days', []),
                "action": intent_data.get('action'),
                "details": intent_data.get('details'),
                "messages": [{"role": "user", "content": user_feedback}]
            }

        return {"intent": "other", "details": "无法解析"}

    except Exception as e:
        print(f"[FAIL] 意图解析错误: {str(e)}")
        return {"intent": "other", "details": str(e)}


async def adjust_plan_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """根据意图调整行程"""
    try:
        current_plan = state.get('final_plan')
        intent = state.get('intent')
        target_days = state.get('target_days', [])
        action = state.get('action')
        details = state.get('details')

        if not current_plan:
            print("[WARN] 无当前行程，无法调整")
            return {}

        print(f"[INFO] 调整行程: {intent} - {details}")

        plan_json = json.dumps(current_plan, ensure_ascii=False, indent=2)

        prompt = ChatPromptTemplate.from_messages([
            ("system", ADJUSTMENT_PROMPT),
            ("user", "请调整行程")
        ])

        chain = prompt | llm.with_structured_output(TripPlan, method="json_mode")

        response = await chain.ainvoke({
            "current_plan": plan_json,
            "intent": intent,
            "target_days": str(target_days),
            "action": action or "adjust_time",
            "details": details or "用户要求调整"
        })

        print("[OK] 行程调整完成")
        return {
            "final_plan": response.model_dump(),
            "iteration_count": state.get('iteration_count', 0) + 1,
            "messages": [{"role": "assistant", "content": f"已根据您的反馈调整行程: {details}"}]
        }

    except Exception as e:
        print(f"[FAIL] 行程调整错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"execution_errors": [f"调整失败: {str(e)}"]}