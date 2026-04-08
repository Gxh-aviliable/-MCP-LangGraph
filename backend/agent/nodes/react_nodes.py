"""ReAct Agent 核心节点

实现真正的 ReAct (Reasoning + Acting) 架构：
- Reasoning: 思考下一步该做什么
- Acting: 执行行动
- Observation: 观察行动结果
- Reflection: 反思结果质量，决定是否继续

这是 Agent 智能的核心体现：
1. 不是硬编码流水线，而是动态决策
2. 每一步都有思考过程
3. 可以根据结果调整后续行动
4. 支持多轮迭代直到满意
"""
import json
import re
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

from backend.agent.state import ChatAgentState
from backend.model import TripPlan
from backend.config.settings import settings


# ==================== 可用行动定义 ====================

ACTIONS = {
    "query_attraction": {
        "description": "查询景点信息",
        "condition": "景点数量不足（少于3个）",
        "tool": "maps_text_search"
    },
    "query_weather": {
        "description": "查询天气预报",
        "condition": "天气信息不完整",
        "tool": "maps_weather"
    },
    "query_hotel": {
        "description": "查询酒店信息",
        "condition": "酒店数量不足（少于3家）",
        "tool": "maps_text_search"
    },
    "query_transport": {
        "description": "查询交通信息（火车票）",
        "condition": "需要交通方案",
        "tool": "12306 tools"
    },
    "generate_plan": {
        "description": "生成行程计划",
        "condition": "信息收集完整，可以生成行程",
        "tool": "llm"
    },
    "evaluate_plan": {
        "description": "评估行程质量",
        "condition": "行程已生成，需要评估质量",
        "tool": "llm"
    },
    "refine_plan": {
        "description": "优化行程",
        "condition": "行程质量不达标，需要改进",
        "tool": "llm"
    },
    "adjust_plan": {
        "description": "调整现有行程",
        "condition": "已有行程，用户提出修改意见",
        "tool": "llm"
    },
    "finish": {
        "description": "完成任务",
        "condition": "行程质量满意，可以结束",
        "tool": None
    }
}


# ==================== 推理节点 ====================

async def reasoning_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """推理节点 - Agent 思考下一步该做什么

    这是真正的智能核心：
    1. 分析当前状态
    2. 评估已有信息
    3. 决定下一步行动
    4. 给出决策理由

    Returns:
        更新后的状态，包含：
        - thoughts: 新增一条思考记录
        - next_action: 决定的下一步行动
        - should_continue: 是否继续推理
    """
    thoughts = state.get('thoughts', [])
    step = len(thoughts) + 1
    iteration_count = state.get('iteration_count', 0)

    # 防止无限循环
    if iteration_count >= 10:
        print(f"[ReAct] 达到最大迭代次数 ({iteration_count})，准备结束")
        return {
            'next_action': 'finish',
            'should_continue': False,
            'quality_score': 0.7
        }

    # 构建上下文
    context = _build_reasoning_context(state)

    prompt = f"""你是一个旅行规划 Agent。请分析当前情况并决定下一步行动。

## 当前状态
{context}

## 可用行动
{_format_available_actions()}

## 决策规则
1. 信息不足时，优先收集信息（景点/天气/酒店/交通）
2. 信息充足时，生成行程
3. 行程质量不佳时，优化行程
4. 质量满意时，结束任务
5. 如果用户特别说明跳过某项，尊重用户选择

## 输出格式 (JSON)
```json
{{
    "thought": "分析当前状态和缺失信息...",
    "action": "选择的行动（如 query_attraction）",
    "action_reason": "选择这个行动的原因",
    "confidence": 0.8,
    "should_continue": true
}}
```

请输出你的决策：
"""

    try:
        response = await llm.ainvoke(prompt)
        result = _parse_json_response(response.content)

        action = result.get('action', 'finish')
        thought = result.get('thought', '')
        confidence = result.get('confidence', 0.5)

        print(f"\n[ReAct Step {step}] 思考: {thought[:100]}...")
        print(f"[ReAct Step {step}] 决策: {action} (置信度: {confidence:.2f})")

        # 记录思考 - 追加到现有列表
        new_thought = {
            'step': step,
            'thought': thought,
            'action': action,
            'action_reason': result.get('action_reason', ''),
            'observation': '',  # 行动后填充
            'reflection': '',   # 观察后填充
            'confidence': confidence
        }

        # 创建更新后的完整 thoughts 列表（追加新的）
        updated_thoughts = thoughts + [new_thought]

        return {
            'thoughts': updated_thoughts,
            'next_action': action,
            'should_continue': result.get('should_continue', True),
            'iteration_count': iteration_count + 1,
        }

    except Exception as e:
        print(f"[ReAct Error] 推理失败: {e}")
        return {
            'next_action': 'finish',
            'should_continue': False,
            'quality_score': 0.3
        }


# ==================== 行动节点 ====================

async def action_node(llm, tools: List, state: ChatAgentState) -> Dict[str, Any]:
    """行动节点 - 执行推理决定的行动

    根据推理结果选择并执行相应的行动：
    - query_attraction: 查询景点
    - query_weather: 查询天气
    - query_hotel: 查询酒店
    - query_transport: 查询交通
    - generate_plan: 生成行程
    - evaluate_plan: 评估行程
    - refine_plan: 优化行程
    - adjust_plan: 调整行程（用户反馈）
    - finish: 不执行行动
    """
    action = state.get('next_action', 'finish')

    print(f"[ReAct] 执行行动: {action}")

    # 行动处理器映射
    action_handlers = {
        'query_attraction': lambda: _handle_query_attraction(llm, tools, state),
        'query_weather': lambda: _handle_query_weather(llm, tools, state),
        'query_hotel': lambda: _handle_query_hotel(llm, tools, state),
        'query_transport': lambda: _handle_query_transport(llm, tools, state),
        'generate_plan': lambda: _handle_generate_plan(llm, state),
        'evaluate_plan': lambda: _handle_evaluate_plan(llm, state),
        'refine_plan': lambda: _handle_refine_plan(llm, state),
        'adjust_plan': lambda: _handle_adjust_plan(llm, state),
        'finish': lambda: {}
    }

    handler = action_handlers.get(action)
    if handler:
        try:
            result = await handler()
            return result
        except Exception as e:
            print(f"[ReAct Error] 行动失败 {action}: {e}")
            return {'execution_errors': [f"{action} 失败: {str(e)}"]}

    return {}


# ==================== 观察节点 ====================

async def observation_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """观察节点 - 评估行动结果

    根据执行的行动类型，评估结果质量：
    - 景点查询：是否有足够的景点？
    - 天气查询：天气信息是否完整？
    - 行程生成：行程是否合理？
    """
    thoughts = state.get('thoughts', [])
    if not thoughts:
        return {}

    last_thought = thoughts[-1]
    action = last_thought.get('action', '')

    # 获取行动结果并生成观察
    observation = _generate_observation(action, state)

    print(f"[ReAct] 观察: {observation[:100]}...")

    # 更新最后一条思考记录的 observation
    thoughts[-1] = {**last_thought, 'observation': observation}

    # 返回更新后的完整 thoughts 列表
    return {'thoughts': thoughts}


# ==================== 反思节点 ====================

async def reflection_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """反思节点 - 决定是否需要继续推理

    这是 Agent 自我反思的核心：
    1. 评估当前结果质量
    2. 判断是否达到目标
    3. 决定是否需要更多行动
    """
    thoughts = state.get('thoughts', [])
    final_plan = state.get('final_plan')
    iteration_count = state.get('iteration_count', 0)

    # 构建反思上下文
    thought_summary = _format_thoughts_summary(thoughts)

    prompt = f"""请反思当前进度并决定是否需要继续。

## 已完成的思考链
{thought_summary}

## 当前数据状态
- 景点: {len(state.get('attractions_data', []))} 个
- 天气: {len(state.get('weather_data', []))} 条
- 酒店: {len(state.get('hotels_data', []))} 家
- 交通: {len(state.get('transport_data', []))} 条
- 行程: {'已生成' if final_plan else '未生成'}

## 反思要点
1. 信息是否足够完整？
2. 行程质量是否满意？
3. 是否还有明显的问题需要解决？

## 输出格式 (JSON)
```json
{{
    "reflection": "反思内容...",
    "quality_score": 0.7,
    "issues": ["问题1", "问题2"],
    "should_continue": false,
    "next_action_if_continue": "建议的下一步行动"
}}
```

请输出你的反思：
"""

    try:
        response = await llm.ainvoke(prompt)
        result = _parse_json_response(response.content)

        should_continue = result.get('should_continue', False)
        quality_score = result.get('quality_score', 0.5)
        reflection = result.get('reflection', '')

        print(f"[ReAct] 反思: {reflection[:100]}...")
        print(f"[ReAct] 质量评分: {quality_score:.2f}, 继续: {should_continue}")

        # 更新最后一条思考记录的 reflection
        if thoughts:
            thoughts[-1] = {**thoughts[-1], 'reflection': reflection}

        return {
            'thoughts': thoughts,
            'should_continue': should_continue,
            'quality_score': quality_score,
            'next_action': result.get('next_action_if_continue', ''),
        }

    except Exception as e:
        print(f"[ReAct Error] 反思失败: {e}")
        return {
            'should_continue': False,
            'quality_score': 0.5
        }


# ==================== 行动处理器 ====================

async def _handle_query_attraction(llm, tools: List, state: ChatAgentState) -> Dict[str, Any]:
    """处理景点查询"""
    city = state.get('city', '')
    interests = state.get('interests', [])

    if not city:
        return {'execution_errors': ['无法查询景点：缺少城市信息']}

    # 查找景点查询工具
    tool = _find_tool(tools, 'maps_text_search')
    if not tool:
        return {'execution_errors': ['景点查询工具不可用']}

    try:
        # 构建查询关键词
        keywords = '景点'
        if interests:
            keywords = ' '.join(interests[:2])

        # 执行工具调用
        from backend.agent.nodes.nodes import create_attraction_node
        node = create_attraction_node(llm, tools)
        result = await node(state)

        attractions = result.get('attractions_data', [])
        print(f"[ReAct] 查询到 {len(attractions)} 个景点")

        return result

    except Exception as e:
        print(f"[ReAct Error] 景点查询失败: {e}")
        return {'attractions_data': []}


async def _handle_query_weather(llm, tools: List, state: ChatAgentState) -> Dict[str, Any]:
    """处理天气查询"""
    city = state.get('city', '')
    start_date = state.get('start_date', '')
    end_date = state.get('end_date', '')

    if not city:
        return {'execution_errors': ['无法查询天气：缺少城市信息']}

    try:
        from backend.agent.nodes.nodes import create_weather_node
        node = create_weather_node(llm, tools)
        result = await node(state)

        weather = result.get('weather_data', [])
        print(f"[ReAct] 查询到 {len(weather)} 条天气信息")

        return result

    except Exception as e:
        print(f"[ReAct Error] 天气查询失败: {e}")
        return {'weather_data': []}


async def _handle_query_hotel(llm, tools: List, state: ChatAgentState) -> Dict[str, Any]:
    """处理酒店查询"""
    city = state.get('city', '')

    if not city:
        return {'execution_errors': ['无法查询酒店：缺少城市信息']}

    try:
        from backend.agent.nodes.nodes import create_hotel_node_v2
        node = create_hotel_node_v2(llm, tools)
        result = await node(state)

        hotels = result.get('hotels_data', [])
        print(f"[ReAct] 查询到 {len(hotels)} 家酒店")

        return result

    except Exception as e:
        print(f"[ReAct Error] 酒店查询失败: {e}")
        return {'hotels_data': []}


async def _handle_query_transport(llm, tools: List, state: ChatAgentState) -> Dict[str, Any]:
    """处理交通查询"""
    origin = state.get('origin', '')
    city = state.get('city', '')
    start_date = state.get('start_date', '')

    if not origin:
        print("[ReAct] 无出发地，跳过交通查询")
        return {'transport_data': []}

    try:
        from backend.agent.nodes.nodes import create_transport_node_v3
        node = create_transport_node_v3(llm, tools)
        result = await node(state)

        transport = result.get('transport_data', [])
        print(f"[ReAct] 查询到 {len(transport)} 条交通方案")

        return result

    except Exception as e:
        print(f"[ReAct Error] 交通查询失败: {e}")
        return {'transport_data': []}


async def _handle_generate_plan(llm, state: ChatAgentState) -> Dict[str, Any]:
    """处理行程生成"""
    try:
        from backend.agent.nodes.nodes import plan_trip_node
        result = await plan_trip_node(llm, state)

        if result.get('final_plan'):
            print("[ReAct] 行程生成成功")
        else:
            print("[ReAct] 行程生成失败")

        return result

    except Exception as e:
        print(f"[ReAct Error] 行程生成失败: {e}")
        return {'execution_errors': [f'行程生成失败: {str(e)}']}


async def _handle_evaluate_plan(llm, state: ChatAgentState) -> Dict[str, Any]:
    """处理行程评估"""
    try:
        from backend.agent.nodes.nodes import reflection_node
        result = await reflection_node(llm, state)

        print(f"[ReAct] 评估完成，质量评分: {result.get('plan_metrics', {}).get('overall_score', 0):.2f}")

        return result

    except Exception as e:
        print(f"[ReAct Error] 行程评估失败: {e}")
        return {'plan_metrics': {'overall_score': 0.5}}


async def _handle_refine_plan(llm, state: ChatAgentState) -> Dict[str, Any]:
    """处理行程优化"""
    try:
        from backend.agent.nodes.nodes import adjust_plan_node

        # 构建调整状态
        adjust_state = {
            **state,
            'intent': 'improve_quality',
            'details': '根据评估结果优化行程'
        }

        result = await adjust_plan_node(llm, adjust_state)
        print("[ReAct] 行程优化完成")

        return result

    except Exception as e:
        print(f"[ReAct Error] 行程优化失败: {e}")
        return {}


async def _handle_adjust_plan(llm, state: ChatAgentState) -> Dict[str, Any]:
    """处理行程调整 - 用户反馈触发的调整"""
    try:
        from backend.agent.nodes.nodes import adjust_plan_node

        user_feedback = state.get('user_feedback', '')
        current_plan = state.get('final_plan')

        print(f"[ReAct] 根据用户反馈调整行程: {user_feedback[:50]}...")

        # 构建调整状态
        adjust_state = {
            **state,
            'final_plan': current_plan,
            'intent': 'modify_schedule',
            'details': user_feedback,
        }

        result = await adjust_plan_node(llm, adjust_state)
        print("[ReAct] 行程调整完成")

        # 返回结果，包含清除 adjustment_request 标记
        return {
            **result,
            'adjustment_request': False,  # 清除标记，表示已处理
            'user_feedback': '',          # 清空反馈
        }

    except Exception as e:
        print(f"[ReAct Error] 行程调整失败: {e}")
        return {
            'execution_errors': [f'行程调整失败: {str(e)}'],
            'adjustment_request': False,
        }


# ==================== 辅助函数 ====================

def _build_reasoning_context(state: ChatAgentState) -> str:
    """构建推理上下文"""
    lines = [
        f"- 目标城市: {state.get('city', '未知')}",
        f"- 出发城市: {state.get('origin', '未知')}",
        f"- 日期: {state.get('start_date', '?')} 至 {state.get('end_date', '?')}",
        f"- 兴趣: {', '.join(state.get('interests', [])) or '未指定'}",
        "",
        "已收集数据:",
        f"- 景点: {len(state.get('attractions_data', []))} 个",
        f"- 天气: {len(state.get('weather_data', []))} 条",
        f"- 酒店: {len(state.get('hotels_data', []))} 家",
        f"- 交通: {len(state.get('transport_data', []))} 条",
        "",
        f"- 行程: {'已生成' if state.get('final_plan') else '未生成'}",
        f"- 迭代次数: {state.get('iteration_count', 0)}",
    ]

    # 用户特别说明
    special = state.get('special_instructions', {})
    if special:
        skips = [k.replace('skip_', '') for k, v in special.items()
                 if k.startswith('skip_') and v]
        if skips:
            lines.append(f"- 用户跳过: {', '.join(skips)}")

    # 【新增】用户反馈处理
    user_feedback = state.get('user_feedback', '')
    adjustment_request = state.get('adjustment_request', False)

    if user_feedback and adjustment_request:
        lines.append("")
        lines.append("【用户反馈】")
        lines.append(f"- 用户说: {user_feedback}")
        lines.append("- 请根据用户反馈决定如何调整行程（adjust_plan 或 refine_plan）")

    return '\n'.join(lines)


def _format_available_actions() -> str:
    """格式化可用行动列表"""
    lines = []
    for action, info in ACTIONS.items():
        lines.append(f"- {action}: {info['description']} (条件: {info['condition']})")
    return '\n'.join(lines)


def _generate_observation(action: str, state: ChatAgentState) -> str:
    """生成观察结果"""
    observations = {
        'query_attraction': f"查询到 {len(state.get('attractions_data', []))} 个景点",
        'query_weather': f"查询到 {len(state.get('weather_data', []))} 条天气信息",
        'query_hotel': f"查询到 {len(state.get('hotels_data', []))} 家酒店",
        'query_transport': f"查询到 {len(state.get('transport_data', []))} 条交通方案",
        'generate_plan': "行程已生成" if state.get('final_plan') else "行程生成失败",
        'evaluate_plan': f"质量评分: {state.get('plan_metrics', {}).get('overall_score', 0):.2f}",
        'refine_plan': "行程已优化",
        'adjust_plan': "行程已根据用户反馈调整",
        'finish': "准备结束"
    }
    return observations.get(action, "行动完成")


def _format_thoughts_summary(thoughts: List[Dict]) -> str:
    """格式化思考链摘要"""
    if not thoughts:
        return "暂无思考记录"

    lines = []
    for t in thoughts[-5:]:  # 最近5条
        step = t.get('step', '?')
        action = t.get('action', '?')
        observation = t.get('observation', '')[:50]
        lines.append(f"Step {step}: {action} -> {observation}...")

    return '\n'.join(lines)


def _parse_json_response(content: str) -> Dict[str, Any]:
    """解析 LLM 响应中的 JSON"""
    try:
        # 尝试直接解析
        return json.loads(content)
    except:
        # 尝试提取 JSON 块
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass

        # 尝试提取 { } 块
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        return {}


def _find_tool(tools: List, name_pattern: str) -> Optional[Any]:
    """查找工具"""
    for tool in tools:
        if name_pattern.lower() in tool.name.lower():
            return tool
    return None