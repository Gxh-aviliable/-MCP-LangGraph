"""LangGraph 状态定义

定义 Agent 执行图中的状态结构
"""
import operator
from typing import Annotated, List, TypedDict, Dict, Any, Optional


class ChatAgentState(TypedDict):
    """多轮对话状态 - 支持持续性交互"""

    # ==================== 用户输入信息 ====================
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

    # ==================== 对话相关 ====================
    messages: Annotated[List[Dict[str, str]], operator.add]  # 对话历史
    user_feedback: Optional[str]                              # 用户最新反馈
    intent: Optional[str]             # 解析出的意图
    target_days: Optional[List[int]]  # 目标天数
    action: Optional[str]             # 操作类型
    details: Optional[str]            # 详细说明

    # ==================== 流程控制 ====================
    iteration_count: int              # 迭代次数
    is_satisfied: bool                # 用户是否满意

    # ==================== 最终结果 ====================
    final_plan: Optional[Dict[str, Any]]                    # 最终行程
    context: Annotated[List[str], operator.add]             # 上下文信息
    execution_errors: Annotated[List[str], operator.add]    # 执行错误


def create_initial_state(request) -> Dict[str, Any]:
    """创建初始状态

    Args:
        request: TripRequest 对象

    Returns:
        初始状态字典
    """
    return {
        # 用户输入
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
        # 对话相关
        "messages": [],
        "user_feedback": None,
        "intent": None,
        "target_days": None,
        "action": None,
        "details": None,
        # 流程控制
        "iteration_count": 0,
        "is_satisfied": False,
        # 最终结果
        "final_plan": None,
        "context": [],
        "execution_errors": [],
    }