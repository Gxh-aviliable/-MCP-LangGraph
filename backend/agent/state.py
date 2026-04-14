"""LangGraph 状态定义

定义 Agent 执行图中的状态结构
"""
import operator
from typing import Annotated, List, TypedDict, Dict, Any, Optional


# ==================== ReAct 思考链 ====================

class AgentThought(TypedDict):
    """Agent 的单步思考记录 - ReAct 架构核心"""
    step: int                    # 第几步
    thought: str                 # 思考内容（分析当前状态）
    action: str                  # 采取的行动
    action_reason: str           # 选择这个行动的原因
    observation: str             # 观察到的结果
    reflection: str              # 反思（这个结果够好吗？）
    confidence: float            # 对当前行动的信心 (0-1)


class ChatAgentState(TypedDict):
    """多轮对话状态 - 支持持续性交互"""

    # ==================== 用户输入信息 ====================
    origin: str                                   # 出发城市（必要字段）
    city: str                                    # 目标城市
    start_date: str                              # 开始日期 YYYY-MM-DD
    end_date: str                                # 结束日期 YYYY-MM-DD
    interests: List[str]                         # 兴趣偏好
    accommodation_type: Optional[str]            # 住宿类型
    budget_per_day: Optional[int]                # 每日预算
    transportation_mode: Optional[str]           # 交通方式

    # ==================== 中间结果 (累加) ====================
    attractions_data: Annotated[List[Dict[str, Any]], operator.add]    # 景点数据
    weather_data: Annotated[List[Dict[str, Any]], operator.add]        # 天气数据
    hotels_data: Annotated[List[Dict[str, Any]], operator.add]         # 酒店数据
    transport_data: Annotated[List[Dict[str, Any]], operator.add]      # 交通数据（火车票/自驾）

    # ==================== 对话相关 ====================
    messages: Annotated[List[Dict[str, str]], operator.add]  # 对话历史
    user_feedback: Optional[str]                              # 用户最新反馈
    intent: Optional[str]             # 解析出的意图
    target_days: Optional[List[int]]  # 目标天数
    action: Optional[str]             # 操作类型
    details: Optional[str]            # 详细说明

    # ==================== 需求收集状态（新增） ====================
    conversation_stage: str           # 对话阶段: greeting/collecting/optional_collecting/confirming/planning/refining/done
    collected_info: Dict[str, Any]    # 已收集的旅行信息
    missing_fields: List[str]         # 缺失的必要字段
    ready_to_plan: bool               # 是否可以开始规划
    user_confirmed: bool              # 用户是否确认生成

    # ==================== 可选参数收集 ====================
    optional_collected: bool          # 可选参数是否已完成（跳过或达到轮次上限）
    optional_skipped: bool            # 用户是否明确跳过可选参数
    optional_round: int               # 当前引导轮次（0表示未开始）

    # ==================== 流程控制 ====================
    iteration_count: int              # 迭代次数
    is_satisfied: bool                # 用户是否满意

    # ==================== Agent 智能决策 ====================
    tool_decisions: Optional[Dict[str, bool]]   # 工具选择决策: {"attraction": True, "weather": True, ...}
    tool_decision_reason: Optional[str]         # 决策原因说明
    special_instructions: Optional[Dict[str, Any]]  # 用户特别说明: {"skip_attraction": True, "reason": "..."}

    # ==================== 反思与重规划 ====================
    need_replan: Optional[bool]                 # 是否需要重新规划
    replan_reason: Optional[str]                # 重规划原因
    replan_attempts: Optional[int]              # 重规划尝试次数
    plan_metrics: Optional[Dict[str, Any]]      # 行程评估指标

    # ==================== ReAct 思考链（核心智能） ====================
    thoughts: List[Dict[str, Any]]                               # 思考历史（不累加，每次替换）
    current_goal: str                                          # 当前目标
    next_action: str                                           # 下一步行动
    should_continue: bool                                      # 是否继续推理
    quality_score: float                                       # 当前质量分数

    # ==================== 最终结果 ====================
    final_plan: Optional[Dict[str, Any]]                    # 最终行程
    context: Annotated[List[str], operator.add]             # 上下文信息
    execution_errors: Annotated[List[str], operator.add]    # 执行错误
    bot_reply: Optional[str]           # 机器人回复（用于响应生成）


# 必要字段列表（出发地为必要字段，用于查询火车票）
REQUIRED_FIELDS = ['origin', 'city', 'start_date', 'end_date']


def create_initial_state(request=None) -> Dict[str, Any]:
    """创建初始状态

    Args:
        request: TripRequest 对象（可选，用于旧的表单模式）

    Returns:
        初始状态字典
    """
    if request:
        # 表单模式：已有完整信息
        return {
            # 用户输入
            "origin": request.origin or "",
            "city": request.city,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "interests": request.interests,
            "accommodation_type": request.accommodation_type,
            "budget_per_day": request.budget_per_day,
            "transportation_mode": request.transportation_mode,
            # 中间结果
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "transport_data": [],
            # 对话相关
            "messages": [],
            "user_feedback": None,
            "intent": None,
            "target_days": None,
            "action": None,
            "details": None,
            # 需求收集
            "conversation_stage": "planning",
            "collected_info": {},
            "missing_fields": [],
            "ready_to_plan": True,
            "user_confirmed": True,
            # 可选参数收集
            "optional_collected": True,  # 表单模式直接跳过可选参数引导
            "optional_skipped": True,
            "optional_round": 0,
            # 流程控制
            "iteration_count": 0,
            "is_satisfied": False,
            # Agent 智能决策
            "tool_decisions": None,
            "tool_decision_reason": None,
            "special_instructions": None,
            # 反思与重规划
            "need_replan": None,
            "replan_reason": None,
            "replan_attempts": 0,
            "plan_metrics": None,
            # ReAct 思考链
            "thoughts": [],
            "current_goal": "",
            "next_action": "",
            "should_continue": True,
            "quality_score": 0.0,
            # 最终结果
            "final_plan": None,
            "context": [],
            "execution_errors": [],
            "bot_reply": None,
        }
    else:
        # 对话模式：从问候开始
        return {
            # 用户输入（初始为空）
            "origin": "",
            "city": "",
            "start_date": "",
            "end_date": "",
            "interests": [],
            "accommodation_type": None,
            "budget_per_day": None,
            "transportation_mode": None,
            # 中间结果
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "transport_data": [],
            # 对话相关
            "messages": [],
            "user_feedback": None,
            "intent": None,
            "target_days": None,
            "action": None,
            "details": None,
            # 需求收集
            "conversation_stage": "greeting",
            "collected_info": {},
            "missing_fields": REQUIRED_FIELDS.copy(),
            "ready_to_plan": False,
            "user_confirmed": False,
            # 可选参数收集
            "optional_collected": False,  # 对话模式需要引导可选参数
            "optional_skipped": False,
            "optional_round": 0,
            # 流程控制
            "iteration_count": 0,
            "is_satisfied": False,
            # Agent 智能决策
            "tool_decisions": None,
            "tool_decision_reason": None,
            "special_instructions": None,
            # 反思与重规划
            "need_replan": None,
            "replan_reason": None,
            "replan_attempts": 0,
            "plan_metrics": None,
            # ReAct 思考链
            "thoughts": [],
            "current_goal": "",
            "next_action": "",
            "should_continue": True,
            "quality_score": 0.0,
            # 最终结果
            "final_plan": None,
            "context": [],
            "execution_errors": [],
            "bot_reply": None,
        }