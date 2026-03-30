# Agent 模块
from .trip_agent import ChatSession, ChatAgentSystem, TripChatSession, TripChatSystem
from .state import ChatAgentState, create_initial_state, REQUIRED_FIELDS

__all__ = [
    'ChatSession', 'ChatAgentSystem',
    'TripChatSession', 'TripChatSystem',  # 兼容旧版本
    'ChatAgentState', 'create_initial_state', 'REQUIRED_FIELDS'
]