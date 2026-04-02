"""工具模块

包含所有 Agent 可用的工具：
- R1 深度分析工具
- MCP 工具管理器
- 工具注册表
- RAG 检索工具
"""
from backend.agent.tools.r1_tool import (
    DeepSeekR1Analyzer,
    get_r1_instance
)

from backend.agent.tools.tool_registry import (
    ToolDefinition,
    AVAILABLE_TOOLS,
    get_tool_by_name,
    get_tools_by_type,
    get_mcp_tools,
    get_tool_names,
    get_tools_description_for_llm
)

from backend.agent.tools.mcp_tools import (
    MCPToolManager,
    get_mcp_manager,
    query_train_tickets,
    query_driving_route,
    query_weather,
    query_lucky_day,
    query_hotels
)

from backend.agent.tools.rag_tool import (
    TravelRAGTool,
    get_rag_instance,
    format_search_results
)

__all__ = [
    # R1 工具
    'DeepSeekR1Analyzer',
    'get_r1_instance',

    # 工具注册表
    'ToolDefinition',
    'AVAILABLE_TOOLS',
    'get_tool_by_name',
    'get_tools_by_type',
    'get_mcp_tools',
    'get_tool_names',
    'get_tools_description_for_llm',

    # MCP 工具
    'MCPToolManager',
    'get_mcp_manager',
    'query_train_tickets',
    'query_driving_route',
    'query_weather',
    'query_lucky_day',
    'query_hotels',

    # RAG 工具
    'TravelRAGTool',
    'get_rag_instance',
    'format_search_results'
]