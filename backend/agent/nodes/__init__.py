"""Agent 节点模块

包含所有 Agent 节点的实现
"""
from .nodes import (
    create_attraction_node,
    create_weather_node,
    create_hotel_node,
    create_hotel_node_v2,  # 【新增】支持周边搜索的酒店节点
    plan_trip_node,
    parse_intent_node,
    adjust_plan_node,
    extract_json_from_text,
    format_attractions,
    format_weather,
    format_hotels,
    summarize_plan,
    # 对话节点
    greeting_node,
    requirement_analyzer_node,
    response_generator_node,
    confirm_check_node,
    stage_router_node,
    optional_guidance_node,  # 【新增】可选参数引导节点
    _all_optional_filled,  # 【新增】检查可选参数是否填满
    # 当前使用的节点
    create_transport_node_v3,
    # 智能规划
    tool_selector_node,
    create_smart_planning_graph,
    # 【新增】Agent智能化节点
    extract_special_instructions,
    reflection_node,
    replan_node,
    create_skip_node,
)

# 【新增】ReAct 节点
from .react_nodes import (
    reasoning_node,
    action_node,
    observation_node,
    # 注意：reflection_node 已在 nodes.py 中定义，这里不重复导出
)

__all__ = [
    'create_attraction_node',
    'create_weather_node',
    'create_hotel_node',
    'create_hotel_node_v2',  # 【新增】支持周边搜索的酒店节点
    'plan_trip_node',
    'parse_intent_node',
    'adjust_plan_node',
    'extract_json_from_text',
    'format_attractions',
    'format_weather',
    'format_hotels',
    'summarize_plan',
    # 对话节点
    'greeting_node',
    'requirement_analyzer_node',
    'response_generator_node',
    'confirm_check_node',
    'stage_router_node',
    'optional_guidance_node',  # 【新增】可选参数引导节点
    '_all_optional_filled',  # 【新增】检查可选参数是否填满
    # 当前使用的节点
    'create_transport_node_v3',
    # 智能规划
    'tool_selector_node',
    'create_smart_planning_graph',
    # 【新增】Agent智能化节点
    'extract_special_instructions',
    'reflection_node',
    'replan_node',
    'create_skip_node',
    # 【新增】ReAct 节点
    'reasoning_node',
    'action_node',
    'observation_node',
]