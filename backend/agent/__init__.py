# Agent 模块
from .trip_agent import (
    ChatSession,
    ChatAgentSystem,
    TripChatSession,
    TripChatSystem,
    SharedResourceManager,  # 新增：共享资源管理器
    ReActChatSession,  # 【新增】ReAct Agent 会话
)
from .state import ChatAgentState, create_initial_state, REQUIRED_FIELDS

__all__ = [
    'ChatSession', 'ChatAgentSystem',
    'TripChatSession', 'TripChatSystem',  # 兼容旧版本
    'SharedResourceManager',  # 新增：共享资源管理器（方案C核心）
    'ReActChatSession',  # 【新增】ReAct Agent 会话
    'ChatAgentState', 'create_initial_state', 'REQUIRED_FIELDS',
]