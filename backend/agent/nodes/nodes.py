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
    TRANSPORT_AGENT_PROMPT,
    TRANSPORT_AGENT_PROMPT_V3,
    LUCKY_DAY_AGENT_PROMPT,
    PLANNER_AGENT_PROMPT,
    INTENT_PARSER_PROMPT,
    ADJUSTMENT_PROMPT,
    REQUIREMENT_ANALYZER_PROMPT,
    RESPONSE_GENERATOR_PROMPT,
    GREETING_MESSAGE,
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

    # 根据节点类型选择合适的工具（不再使用危险的 fallback）
    required_tool_name = None
    if "景点" in node_name or "attraction" in output_key:
        required_tool_name = "maps_text_search"
    elif "天气" in node_name or "weather" in output_key:
        required_tool_name = "maps_weather"
    elif "酒店" in node_name or "hotel" in output_key:
        required_tool_name = "maps_text_search"

    if required_tool_name:
        tool = tool_name_map.get(required_tool_name)
        if not tool:
            raise ValueError(
                f"{node_name} 需要的工具 '{required_tool_name}' 未加载。"
                f"可用工具: {list(tool_name_map.keys())}"
            )
        filtered_tools = [tool]
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
        transport_data = state.get('transport_data', [])
        lucky_day_data = state.get('lucky_day_data', [])

        print(f"   景点: {len(attractions)} 条, 天气: {len(weather_info)} 条, 酒店: {len(hotels)} 条")
        print(f"   交通: {len(transport_data)} 条, 黄历: {len(lucky_day_data)} 条")

        planner_prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_AGENT_PROMPT),
            ("user", "{context}")
        ])

        planner_chain = planner_prompt | llm.with_structured_output(TripPlan, method="json_mode")

        attractions_summary = format_attractions(attractions)
        weather_summary = format_weather(weather_info)
        hotels_summary = format_hotels(hotels)

        # 格式化交通信息
        transport_summary = "暂无交通信息"
        if transport_data:
            transport_lines = []
            for t in transport_data[:5]:
                transport_lines.append(f"- {t.get('name', '未知')}: 耗时{t.get('duration', '未知')}, 费用{t.get('cost', 0)}元")
            transport_summary = "\n".join(transport_lines)

        # 格式化黄历信息
        lucky_summary = "暂无黄历信息"
        if lucky_day_data:
            lucky_info = lucky_day_data[0]
            lucky_summary = lucky_info.get('summary', '')

        res = await planner_chain.ainvoke({
            "context": f"""
根据以下信息为用户生成详细的旅行计划：

[用户需求]
- 出发地: {state.get('origin', '未指定')}
- 目的地: {state['city']}
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

【交通方案】
{transport_summary}

【黄历参考】
{lucky_summary}

请生成完整的 {trip_days} 天行程计划。
"""
        })

        # 获取生成的计划并填充额外字段
        plan_dict = res.model_dump()

        # 填充交通方案
        if transport_data:
            plan_dict['transport_options'] = [
                {
                    "type": t.get('type', 'unknown'),
                    "name": t.get('name', ''),
                    "duration": t.get('duration', ''),
                    "cost": t.get('cost', 0),
                    "details": t.get('details', {})
                }
                for t in transport_data
            ]

        # 填充黄历信息
        if lucky_day_data:
            plan_dict['lucky_day_info'] = lucky_day_data[0]

        # 填充出发地
        plan_dict['origin'] = state.get('origin', '')

        print("[OK] 行程规划完成")
        return {
            "final_plan": plan_dict,
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
            ("user", """请根据以下信息调整行程：

当前行程JSON:
{current_plan}

用户意图: {intent}
目标天数: {target_days}
操作类型: {action}
详细说明: {details}

请输出调整后的完整行程JSON。""")
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


# ===================== 对话式需求收集节点 =====================

async def greeting_node(state: ChatAgentState) -> Dict[str, Any]:
    """问候节点 - 初始化对话"""
    print("\n[Greeting] 发送问候消息...")
    return {
        "bot_reply": GREETING_MESSAGE,
        "conversation_stage": "greeting",
        "messages": [{"role": "assistant", "content": GREETING_MESSAGE}]
    }


async def requirement_analyzer_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """需求分析节点 - 解析用户消息，提取旅行信息"""
    try:
        user_message = state.get('user_feedback', '')
        collected_info = state.get('collected_info', {})
        current_date = datetime.now().strftime('%Y-%m-%d')

        if not user_message:
            return {"conversation_stage": "collecting"}

        print(f"\n[Analyzer] 分析用户消息: {user_message}")

        # 格式化已收集信息
        collected_str = json.dumps(collected_info, ensure_ascii=False) if collected_info else "暂无"

        prompt = ChatPromptTemplate.from_messages([
            ("system", REQUIREMENT_ANALYZER_PROMPT),
            ("user", "分析用户消息并提取旅行信息")
        ])

        chain = prompt | llm

        response = await chain.ainvoke({
            "current_date": current_date,
            "collected_info": collected_str,
            "user_message": user_message
        })

        content = response.content
        json_match = re.search(r'\{[\s\S]*\}', content)

        if json_match:
            result = json.loads(json_match.group())
            extracted = result.get('extracted', {})
            missing = result.get('missing', [])
            ready = result.get('ready', False)
            suggestions = result.get('suggestions', [])

            # 合并已收集信息和新提取的信息
            new_collected = {**collected_info}
            for key, value in extracted.items():
                if value is not None and value != [] and value != "":
                    new_collected[key] = value

            print(f"[OK] 提取信息: {extracted}, 缺失: {missing}, 就绪: {ready}")

            # 更新状态字段
            origin = new_collected.get('origin', '')
            city = new_collected.get('city', '')
            start_date = new_collected.get('start_date', '')
            end_date = new_collected.get('end_date', '')

            return {
                "collected_info": new_collected,
                "missing_fields": missing,
                "ready_to_plan": ready,
                "origin": origin,
                "city": city,
                "start_date": start_date,
                "end_date": end_date,
                "interests": new_collected.get('interests', []),
                "budget_per_day": new_collected.get('budget_per_day'),
                "accommodation_type": new_collected.get('accommodation_type'),
                "messages": [{"role": "user", "content": user_message}],
                "conversation_stage": "confirming" if ready else "collecting",
            }

        return {"conversation_stage": "collecting"}

    except Exception as e:
        print(f"[FAIL] 需求分析错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"conversation_stage": "collecting", "execution_errors": [f"分析失败: {str(e)}"]}


async def response_generator_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """响应生成节点 - 根据对话阶段生成回复"""
    try:
        stage = state.get('conversation_stage', 'greeting')
        collected_info = state.get('collected_info', {})
        missing_fields = state.get('missing_fields', [])
        user_message = state.get('user_feedback', '')
        current_plan = state.get('final_plan')

        print(f"\n[Response] 生成回复, 阶段: {stage}")

        # 格式化参数
        collected_str = json.dumps(collected_info, ensure_ascii=False, indent=2) if collected_info else "暂无"
        missing_str = ", ".join(missing_fields) if missing_fields else "无"
        plan_summary = summarize_plan(current_plan) if current_plan else "暂无行程"

        prompt = ChatPromptTemplate.from_messages([
            ("system", RESPONSE_GENERATOR_PROMPT),
            ("user", "根据对话阶段生成回复")
        ])

        chain = prompt | llm

        response = await chain.ainvoke({
            "stage": stage,
            "collected_info": collected_str,
            "missing_fields": missing_str,
            "user_message": user_message,
            "plan_summary": plan_summary
        })

        content = response.content
        json_match = re.search(r'\{[\s\S]*\}', content)

        if json_match:
            result = json.loads(json_match.group())
            reply = result.get('reply', '请告诉我您的旅行需求。')
            # 安全打印，避免Windows终端编码错误
            try:
                safe_reply = reply[:50].encode('utf-8', errors='replace').decode('utf-8')
                print(f"[OK] 生成回复: {safe_reply}...")
            except:
                print(f"[OK] 生成回复: (包含特殊字符)")
            return {
                "bot_reply": reply,
                "messages": [{"role": "assistant", "content": reply}]
            }

        # 如果无法解析，返回默认回复
        default_reply = "请告诉我您想去哪里旅行？"
        return {
            "bot_reply": default_reply,
            "messages": [{"role": "assistant", "content": default_reply}]
        }

    except Exception as e:
        print(f"[FAIL] 响应生成错误: {str(e)}")
        return {
            "bot_reply": "抱歉，我遇到了一些问题。请重新描述您的需求。",
            "messages": [{"role": "assistant", "content": "抱歉，我遇到了一些问题。请重新描述您的需求。"}]
        }


async def confirm_check_node(state: ChatAgentState) -> str:
    """确认检查节点 - 判断用户是否确认生成计划"""
    user_message = state.get('user_feedback', '').strip().lower()
    confirm_keywords = ['是', '好', '生成', '可以', '确认', '没问题', 'ok', 'yes', '开始']

    # 检查是否包含确认关键词
    for keyword in confirm_keywords:
        if keyword in user_message:
            return "confirmed"

    # 检查是否是拒绝
    reject_keywords = ['不', '否', '取消', '等等', '再想想']
    for keyword in reject_keywords:
        if keyword in user_message:
            return "rejected"

    return "pending"


async def stage_router_node(state: ChatAgentState) -> str:
    """阶段路由节点 - 根据状态决定下一步"""
    stage = state.get('conversation_stage', 'greeting')
    ready_to_plan = state.get('ready_to_plan', False)
    user_confirmed = state.get('user_confirmed', False)
    has_plan = state.get('final_plan') is not None

    # 如果已有行程，检查是否需要调整
    if has_plan:
        user_feedback = state.get('user_feedback', '')
        if user_feedback and user_feedback.strip() not in ['确认', '满意', '好的']:
            return "refining"
        return "done"

    # 根据阶段路由
    if stage == "greeting":
        return "collecting"

    if stage == "collecting":
        if ready_to_plan:
            return "confirming"
        return "collecting"

    if stage == "confirming":
        if user_confirmed:
            return "planning"
        return "confirming"

    if stage == "planning":
        return "planning"

    return "collecting"


# ===================== 交通查询节点 =====================

def create_transport_node_v3(llm, mcp_client):
    """创建交通专家节点 V3 - 使用 LLM + 工具调用

    与景点专家类似的架构，更健壮的错误处理
    """
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
    import asyncio

    prompt = ChatPromptTemplate.from_messages([
        ("system", TRANSPORT_AGENT_PROMPT_V3),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    async def node(state: ChatAgentState) -> Dict[str, Any]:
        try:
            origin = state.get('origin', '')
            destination = state.get('city', '')
            start_date = state.get('start_date', '')

            print(f"\n[Transport] 查询交通: {origin} -> {destination}, 日期: {start_date}")

            if not origin:
                print("[Transport] 无出发地，跳过交通查询")
                return {"transport_data": []}

            # 获取 12306 工具
            try:
                train_tools = await mcp_client.get_tools(server_name="12306 Server")
                print(f"[Transport] 获取到 {len(train_tools)} 个 12306 工具")
            except Exception as e:
                print(f"[Transport] 获取 12306 工具失败: {e}")
                return {"transport_data": []}

            # 过滤出需要的工具
            filtered_tools = []
            for tool in train_tools:
                name_lower = tool.name.lower()
                if "station" in name_lower or "ticket" in name_lower:
                    if "interline" not in name_lower:
                        filtered_tools.append(tool)

            if not filtered_tools:
                print("[Transport] 未找到可用的交通查询工具")
                return {"transport_data": []}

            print(f"[Transport] 使用工具: {[t.name for t in filtered_tools]}")

            agent = create_tool_calling_agent(llm, filtered_tools, prompt)
            executor = AgentExecutor(
                agent=agent,
                tools=filtered_tools,
                verbose=settings.debug,
                max_iterations=5,
                handle_parsing_errors=True
            )

            input_str = f"""请查询从 {origin} 到 {destination} 的火车票，出发日期：{start_date}

步骤：
1. 调用 get-stations-code-in-city 获取 {origin} 的站点代码
2. 调用 get-stations-code-in-city 获取 {destination} 的站点代码
3. 调用 get-tickets 查询车票（参数：fromStation, toStation, date）

最后将结果整理成 JSON 数组输出。"""

            # 添加超时保护（60秒）
            try:
                result = await asyncio.wait_for(
                    executor.ainvoke({"input": input_str}),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                print("[Transport] 查询超时（60秒），跳过交通查询")
                return {"transport_data": []}

            output_text = result.get('output', '')

            # 提取 JSON 数据
            structured_data = extract_json_from_text(output_text)

            # 转换为标准格式
            transport_results = []
            for item in structured_data:
                if isinstance(item, dict):
                    transport_results.append({
                        "type": item.get("type", "train"),
                        "name": item.get("name", item.get("trainCode", item.get("train_code", "未知"))),
                        "duration": item.get("duration", item.get("runTime", "")),
                        "cost": item.get("cost", item.get("price", 0)),
                        "details": item
                    })

            print(f"[OK] Transport 查询到 {len(transport_results)} 条交通方案")
            return {"transport_data": transport_results}

        except Exception as e:
            print(f"[FAIL] 交通查询错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"transport_data": []}

    return node


async def create_transport_node(mcp_manager):
    """创建交通查询节点（旧版，已废弃）"""
    pass


async def create_transport_node_v2(mcp_client, state: ChatAgentState) -> Dict[str, Any]:
    """交通查询节点 V2 - 使用 MultiServerMCPClient

    Args:
        mcp_client: MultiServerMCPClient 实例
        state: 当前状态

    Returns:
        包含交通数据的字典
    """
    try:
        origin = state.get('origin', '')
        destination = state.get('city', '')
        start_date = state.get('start_date', '')

        print(f"\n[Transport] 查询交通: {origin} -> {destination}, 日期: {start_date}")

        if not origin:
            print("[Transport] 无出发地，跳过交通查询")
            return {"transport_data": []}

        transport_results = []

        # 获取 12306 服务器的工具
        try:
            train_tools = await mcp_client.get_tools(server_name="12306 Server")
            print(f"[Transport] 获取到 {len(train_tools)} 个 12306 工具")

            # 打印所有工具名称和参数
            tool_info = {}
            for tool in train_tools:
                tool_info[tool.name] = tool
                desc = tool.description[:80] if tool.description else "N/A"
                print(f"  - {tool.name}: {desc}")

            # 尝试查找站点查询工具 - 用于获取站点代码
            station_code_tool = None
            for name, tool in tool_info.items():
                name_lower = name.lower()
                if "station" in name_lower and "city" in name_lower:
                    station_code_tool = tool
                    print(f"[Transport] 找到站点代码工具: {name}")
                    break

            # 尝试查找车票查询工具
            ticket_tool = None
            for name, tool in tool_info.items():
                name_lower = name.lower()
                if "ticket" in name_lower and "interline" not in name_lower:
                    ticket_tool = tool
                    print(f"[Transport] 找到车票工具: {name}")
                    break

            # 如果找到了站点代码工具，先获取站点代码
            from_station_code = None
            to_station_code = None

            if station_code_tool:
                print(f"[Transport] 获取站点代码...")
                try:
                    # 获取出发城市站点代码
                    origin_result = await station_code_tool.ainvoke({"city": origin})
                    origin_codes = _parse_station_codes(origin_result)
                    if origin_codes:
                        from_station_code = origin_codes[0]
                        print(f"[Transport] {origin} 站点代码: {from_station_code}")

                    # 获取目的城市站点代码
                    dest_result = await station_code_tool.ainvoke({"city": destination})
                    dest_codes = _parse_station_codes(dest_result)
                    if dest_codes:
                        to_station_code = dest_codes[0]
                        print(f"[Transport] {destination} 站点代码: {to_station_code}")

                except Exception as e:
                    print(f"[Transport] 站点代码查询失败: {e}")

            # 如果找到了车票工具且有站点代码，查询车票
            if ticket_tool and from_station_code and to_station_code:
                print(f"[Transport] 使用车票工具: {ticket_tool.name}")
                try:
                    # 使用正确的参数: fromStation, toStation, date
                    params = {
                        "fromStation": from_station_code,
                        "toStation": to_station_code,
                        "date": start_date
                    }
                    print(f"[Transport] 查询参数: {params}")
                    result = await ticket_tool.ainvoke(params)
                    tickets_data = _parse_tickets_result(result)

                    for ticket in tickets_data[:5]:
                        transport_results.append({
                            "type": "train",
                            "name": ticket.get('trainCode', ticket.get('train_code', ticket.get('trainNo', '未知'))),
                            "duration": ticket.get('duration', ticket.get('runTime', '')),
                            "cost": ticket.get('price', 0),
                            "details": ticket
                        })

                    print(f"[Transport] 查询到 {len(tickets_data)} 个车次")

                except Exception as e:
                    print(f"[Transport] 车票查询失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                if not station_code_tool:
                    print("[Transport] 未找到站点代码工具")
                if not from_station_code or not to_station_code:
                    print(f"[Transport] 站点代码获取失败: from={from_station_code}, to={to_station_code}")

        except Exception as e:
            print(f"[Transport] 12306 查询失败: {e}")

        # 尝试获取自驾路线（从高德地图工具）
        try:
            amap_tools = await mcp_client.get_tools(server_name="amap")
            geo_tool = None
            driving_tool = None

            for tool in amap_tools:
                if "geo" in tool.name.lower():
                    geo_tool = tool
                elif "driving" in tool.name.lower():
                    driving_tool = tool

            if geo_tool and driving_tool:
                # 获取经纬度
                origin_geo = await geo_tool.ainvoke({"address": origin})
                dest_geo = await geo_tool.ainvoke({"address": destination})

                origin_coords = _extract_coords(origin_geo)
                dest_coords = _extract_coords(dest_geo)

                if origin_coords and dest_coords:
                    driving_result = await driving_tool.ainvoke({
                        "origin": origin_coords,
                        "destination": dest_coords
                    })
                    driving_data = _parse_driving_result(driving_result)

                    if driving_data:
                        transport_results.append({
                            "type": "driving",
                            "name": f"自驾: {origin} -> {destination}",
                            "duration": driving_data.get('duration', ''),
                            "cost": driving_data.get('tolls', 0),
                            "details": driving_data
                        })
                        print(f"[Transport] 自驾路线: {driving_data.get('distance', '未知')} 公里")

        except Exception as e:
            print(f"[Transport] 自驾路线查询失败: {e}")

        print(f"[OK] Transport 共查询到 {len(transport_results)} 条交通方案")
        return {"transport_data": transport_results}

    except Exception as e:
        print(f"[FAIL] 交通查询错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"transport_data": []}


def _parse_station_codes(result: Any) -> List[str]:
    """解析站点代码结果"""
    try:
        if isinstance(result, str):
            data = json.loads(result)
        else:
            data = result

        if isinstance(data, dict):
            if 'return' in data:
                stations = data['return']
            elif 'data' in data:
                stations = data['data']
            else:
                stations = data
        else:
            stations = data

        if isinstance(stations, list):
            codes = []
            for station in stations:
                if isinstance(station, dict):
                    code = station.get('station_code') or station.get('code') or station.get('telecode')
                    if code:
                        codes.append(code)
            return codes
        return []
    except:
        return []


def _parse_tickets_result(result: Any) -> List[Dict]:
    """解析火车票查询结果"""
    try:
        if isinstance(result, str):
            data = json.loads(result)
        else:
            data = result

        if isinstance(data, dict):
            if 'return' in data:
                return data['return'] if isinstance(data['return'], list) else []
            if 'data' in data:
                return data['data'] if isinstance(data['data'], list) else []
        if isinstance(data, list):
            return data
        return []
    except:
        return []


def _extract_coords(geo_result: Any) -> Optional[str]:
    """从地理编码结果中提取坐标"""
    try:
        if isinstance(geo_result, str):
            data = json.loads(geo_result)
        else:
            data = geo_result

        if isinstance(data, dict) and 'return' in data:
            if isinstance(data['return'], list) and len(data['return']) > 0:
                return data['return'][0].get('location')
        return None
    except:
        return None


def _parse_driving_result(result: Any) -> Optional[Dict]:
    """解析自驾路线结果"""
    try:
        if isinstance(result, str):
            data = json.loads(result)
        else:
            data = result

        if isinstance(data, dict) and 'return' in data:
            route = data['return']
            if isinstance(route, list) and len(route) > 0:
                route_info = route[0]
                return {
                    "distance": route_info.get('distance', ''),
                    "duration": route_info.get('duration', ''),
                    "tolls": route_info.get('tolls', 0),
                    "route": route_info.get('strategy', '')
                }
        return None
    except:
        return None


# ===================== 黄历查询节点 =====================

async def create_lucky_day_node(mcp_manager):
    """创建黄历查询节点（旧版，已废弃）"""
    pass


async def create_lucky_day_node_v2(mcp_client, state: ChatAgentState) -> Dict[str, Any]:
    """黄历查询节点 V2 - 使用 MultiServerMCPClient

    Args:
        mcp_client: MultiServerMCPClient 实例
        state: 当前状态

    Returns:
        包含黄历数据的字典
    """
    try:
        start_date = state.get('start_date', '')

        print(f"\n[LuckyDay] 查询黄历: {start_date}")

        if not start_date:
            print("[LuckyDay] 无出发日期，跳过黄历查询")
            return {"lucky_day_data": []}

        lucky_results = []

        try:
            # 获取 bazi 服务器的工具
            bazi_tools = await mcp_client.get_tools(server_name="bazi Server")
            print(f"[LuckyDay] 获取到 {len(bazi_tools)} 个 bazi 工具")

            # 找到黄历查询工具
            calendar_tool = None
            for tool in bazi_tools:
                if "calendar" in tool.name.lower() or "chinese" in tool.name.lower():
                    calendar_tool = tool
                    break

            if calendar_tool:
                # 转换为 ISO 格式
                iso_date = f"{start_date}T12:00:00+08:00"
                result = await calendar_tool.ainvoke({"solarDatetime": iso_date})

                # 解析结果
                lucky_info = _parse_lucky_day_result(result, start_date)

                if lucky_info:
                    lucky_results.append(lucky_info)
                    print(f"[OK] LuckyDay 查询成功: {lucky_info['summary'][:30]}...")
                else:
                    print("[LuckyDay] 解析黄历数据失败")

        except Exception as e:
            print(f"[LuckyDay] 黄历查询失败: {e}")

        return {"lucky_day_data": lucky_results}

    except Exception as e:
        print(f"[FAIL] 黄历查询错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"lucky_day_data": []}


def _parse_lucky_day_result(result: Any, date: str) -> Optional[Dict[str, Any]]:
    """解析黄历查询结果"""
    try:
        if isinstance(result, str):
            data = json.loads(result)
        else:
            data = result

        # 尝试从不同格式中提取数据
        if isinstance(data, dict):
            lunar_date = data.get('lunarDate', data.get('lunar_date', ''))
            gan_zhi = data.get('ganZhi', data.get('gan_zhi', ''))
            suitable = data.get('yi', data.get('suitable', []))
            avoid = data.get('ji', data.get('avoid', []))
        else:
            return None

        # 确保是列表格式
        if isinstance(suitable, str):
            suitable = [s.strip() for s in suitable.split('、') if s.strip()]
        if isinstance(avoid, str):
            avoid = [a.strip() for a in avoid.split('、') if a.strip()]

        # 生成摘要
        suitable_str = '、'.join(suitable[:5]) if suitable else '无'
        avoid_str = '、'.join(avoid[:5]) if avoid else '无'

        # 检查是否适合出行
        travel_keywords = ['出行', '旅游', '远行']
        is_suitable_for_travel = any(kw in str(suitable) for kw in travel_keywords)
        is_avoid_travel = any(kw in str(avoid) for kw in travel_keywords)

        if is_suitable_for_travel:
            summary = f"宜出行。农历{lunar_date}，{gan_zhi}。宜：{suitable_str}"
        elif is_avoid_travel:
            summary = f"忌出行，建议另选吉日。农历{lunar_date}，{gan_zhi}。忌：{avoid_str}"
        else:
            summary = f"农历{lunar_date}，{gan_zhi}。宜：{suitable_str}；忌：{avoid_str}"

        return {
            "date": date,
            "lunar_date": lunar_date,
            "gan_zhi": gan_zhi,
            "suitable": suitable,
            "avoid": avoid,
            "summary": summary
        }
    except Exception as e:
        print(f"[LuckyDay] 解析错误: {e}")
        return None