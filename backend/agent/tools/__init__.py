"""工具模块

包含所有 Agent 可用的工具：
- MCP 工具管理器
"""
from backend.agent.tools.mcp_tools import (
    MCPToolManager,
    get_mcp_manager,
    query_train_tickets,
    query_driving_route,
    query_weather,
    query_hotels
)

__all__ = [
    # MCP 工具
    'MCPToolManager',
    'get_mcp_manager',
    'query_train_tickets',
    'query_driving_route',
    'query_weather',
    'query_hotels',
]