"""MCP 工具管理器

管理所有 MCP 服务器连接，提供统一的工具调用接口
支持自动重试和超时保护
"""
import json
import os
import asyncio
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack
from datetime import datetime

from backend.config.settings import settings
from backend.agent.tools.tool_registry import AVAILABLE_TOOLS, ToolDefinition


class MCPToolManager:
    """MCP 工具管理器 - 管理所有 MCP 服务器连接

    功能：
    - 统一的 MCP 服务器连接管理
    - 带重试机制的工具调用
    - 超时保护
    - 错误恢复
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or settings.mcp_config_path
        self.mcp_servers: Dict[str, Any] = {}
        self.exit_stack: Optional[AsyncExitStack] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """初始化所有 MCP 服务器连接

        Returns:
            是否成功初始化至少一个服务器
        """
        if self._initialized:
            return len(self.mcp_servers) > 0

        # 获取项目根目录（backend 的父目录）
        # __file__ = backend/agent/tools/mcp_tools.py
        # dirname(__file__) = backend/agent/tools
        # dirname 3次 = backend，但配置路径已经是 backend/config/...
        # 所以只需要 dirname 2次，得到 backend/agent，然后拼接到项目根
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        config_full_path = os.path.join(project_root, self.config_path)

        if not os.path.exists(config_full_path):
            print(f"[MCP] 配置文件不存在: {config_full_path}")
            return False

        with open(config_full_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        self.exit_stack = AsyncExitStack()
        success_count = 0

        for server_conf in config.get("mcp_servers", []):
            name = server_conf.get("name")
            url = server_conf.get("url", "")
            enabled = server_conf.get("enabled", True)

            if not enabled:
                print(f"[MCP] 跳过禁用的服务器: {name}")
                continue

            if not url or url.startswith("${"):
                print(f"[MCP] 服务器 {name} URL 未配置，跳过")
                continue

            try:
                # 使用 SSE 连接 MCP 服务器
                from agents.mcp import MCPServerSse

                server = await self.exit_stack.enter_async_context(
                    MCPServerSse(name=name, params={"url": url})
                )
                self.mcp_servers[name] = server
                success_count += 1
                print(f"[MCP] 连接成功: {name}")

            except ImportError:
                print(f"[MCP] 未安装 agents.mcp，使用本地工具模式")
                break
            except Exception as e:
                print(f"[MCP] 连接失败 {name}: {str(e)}")

        self._initialized = True
        return success_count > 0

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        max_retries: int = 2,
        timeout: float = 60.0,
        **kwargs
    ) -> str:
        """调用 MCP 工具，带重试机制

        Args:
            server_name: MCP 服务器名称
            tool_name: 工具名称
            max_retries: 最大重试次数（默认2次）
            timeout: 超时时间（秒）
            **kwargs: 工具参数

        Returns:
            工具调用结果（JSON字符串）
        """
        if server_name not in self.mcp_servers:
            return json.dumps({
                "error": f"MCP服务器 {server_name} 未连接",
                "available_servers": list(self.mcp_servers.keys())
            }, ensure_ascii=False)

        last_error = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    print(f"[MCP] 第{attempt}次重试 {server_name}.{tool_name}...")
                    await asyncio.sleep(1 * attempt)  # 指数退避

                # 带超时的调用
                result = await asyncio.wait_for(
                    self.mcp_servers[server_name].call_tool(
                        tool_name,
                        arguments=kwargs
                    ),
                    timeout=timeout
                )

                # 处理 MCP 返回的 CallToolResult 对象
                return self._parse_mcp_result(result)

            except asyncio.TimeoutError:
                last_error = TimeoutError(f"工具调用超时 ({timeout}秒)")
                print(f"[MCP] {server_name}.{tool_name} 超时")

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # 判断是否是可重试的错误
                is_retryable = any([
                    "peer closed connection" in error_str,
                    "incomplete chunked read" in error_str,
                    "remoteprotocolerror" in error_str,
                    "connection reset" in error_str
                ])

                if is_retryable and attempt < max_retries:
                    print(f"[MCP] {server_name}.{tool_name} 连接中断，将重试...")
                    continue
                else:
                    break

        # 所有重试均失败
        return json.dumps({
            "error": f"工具调用失败: {str(last_error)}",
            "server": server_name,
            "tool": tool_name,
            "retries": max_retries
        }, ensure_ascii=False)

    def _parse_mcp_result(self, result: Any) -> str:
        """解析 MCP 工具返回结果"""
        if hasattr(result, 'content'):
            content = result.content
            if isinstance(content, list) and len(content) > 0:
                if hasattr(content[0], 'text'):
                    return content[0].text
                else:
                    return str(content[0])
            elif isinstance(content, str):
                return content
            else:
                return json.dumps(content, ensure_ascii=False, indent=2)
        else:
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    async def list_tools(self, server_name: str) -> List[str]:
        """列出指定服务器的可用工具"""
        if server_name not in self.mcp_servers:
            return []

        try:
            tools = await self.mcp_servers[server_name].list_tools()
            tool_names = []
            for tool in tools:
                if hasattr(tool, 'name'):
                    tool_names.append(tool.name)
                elif isinstance(tool, dict) and 'name' in tool:
                    tool_names.append(tool['name'])
            return tool_names
        except Exception as e:
            print(f"[MCP] 获取工具列表失败: {e}")
            return []

    async def cleanup(self):
        """清理资源"""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
            except Exception:
                pass
        self.mcp_servers.clear()
        self._initialized = False


# ==================== 工具调用辅助函数 ====================

async def query_train_tickets(
    manager: MCPToolManager,
    origin: str,
    destination: str,
    date: str
) -> Dict[str, Any]:
    """查询火车票（含站点代码转换）

    Args:
        manager: MCP 工具管理器
        origin: 出发城市
        destination: 目的地城市
        date: 出发日期

    Returns:
        包含火车票和自驾路线的结果
    """
    result = {
        "train": None,
        "driving": None,
        "error": None
    }

    try:
        # 修正日期年份
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            current_year = datetime.now().year
            if date_obj.year < current_year:
                date = date.replace(str(date_obj.year), str(current_year))
        except:
            pass

        # 1. 获取站点代码
        from_codes = await _get_station_codes(manager, origin)
        to_codes = await _get_station_codes(manager, destination)

        print(f"[Train] 站点代码: {origin}={from_codes}, {destination}={to_codes}")

        # 2. 查询火车票
        if from_codes and to_codes:
            train_result = await manager.call_tool(
                "12306 Server",
                "get-tickets",
                fromStation=from_codes[0] if isinstance(from_codes, list) else from_codes,
                toStation=to_codes[0] if isinstance(to_codes, list) else to_codes,
                date=date
            )
            result["train"] = json.loads(train_result) if isinstance(train_result, str) else train_result

        # 3. 查询自驾路线
        driving_result = await query_driving_route(manager, origin, destination)
        result["driving"] = driving_result

    except Exception as e:
        result["error"] = str(e)

    return result


async def _get_station_codes(manager: MCPToolManager, city: str) -> Optional[List[str]]:
    """获取城市的站点代码"""
    try:
        codes_result = await manager.call_tool(
            "12306 Server",
            "get-stations-code-in-city",
            city=city
        )

        if codes_result and "error" not in str(codes_result).lower():
            codes_data = json.loads(codes_result) if isinstance(codes_result, str) else codes_result

            if isinstance(codes_data, list):
                codes = []
                for station in codes_data:
                    code = station.get('station_code') or station.get('code') or station.get('telecode')
                    if code:
                        codes.append(code)
                return codes

        return None
    except Exception as e:
        print(f"[Train] 获取站点代码失败: {e}")
        return None


async def query_driving_route(
    manager: MCPToolManager,
    origin: str,
    destination: str
) -> Optional[Dict[str, Any]]:
    """查询自驾路线

    Args:
        manager: MCP 工具管理器
        origin: 出发地（城市名）
        destination: 目的地（城市名）

    Returns:
        自驾路线信息
    """
    try:
        # 1. 获取经纬度
        origin_geo = await manager.call_tool("Gaode Server", "maps_geo", address=origin)
        dest_geo = await manager.call_tool("Gaode Server", "maps_geo", address=destination)

        origin_coords = _extract_location(origin_geo)
        dest_coords = _extract_location(dest_geo)

        if not origin_coords or not dest_coords:
            return None

        # 2. 查询自驾路线
        driving_result = await manager.call_tool(
            "Gaode Server",
            "maps_direction_driving",
            origin=origin_coords,
            destination=dest_coords
        )

        return json.loads(driving_result) if isinstance(driving_result, str) else driving_result

    except Exception as e:
        print(f"[Driving] 查询失败: {e}")
        return None


def _extract_location(geo_result: str) -> Optional[str]:
    """从地理编码结果中提取坐标"""
    try:
        data = json.loads(geo_result) if isinstance(geo_result, str) else geo_result
        if isinstance(data, dict) and 'return' in data:
            if isinstance(data['return'], list) and len(data['return']) > 0:
                return data['return'][0].get('location')
        return None
    except:
        return None


async def query_weather(
    manager: MCPToolManager,
    city: str
) -> Optional[Dict[str, Any]]:
    """查询天气"""
    try:
        result = await manager.call_tool("Gaode Server", "maps_weather", city=city)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        print(f"[Weather] 查询失败: {e}")
        return None


async def query_lucky_day(
    manager: MCPToolManager,
    date: str
) -> Optional[Dict[str, Any]]:
    """查询黄历"""
    try:
        # 转换为 ISO 格式
        iso_date = f"{date}T12:00:00+08:00"
        result = await manager.call_tool("bazi Server", "getChineseCalendar", solarDatetime=iso_date)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        print(f"[LuckyDay] 查询失败: {e}")
        return None


async def query_hotels(
    manager: MCPToolManager,
    city: str,
    keywords: str = "酒店"
) -> Optional[Dict[str, Any]]:
    """查询酒店"""
    try:
        if "酒店" not in keywords and "民宿" not in keywords:
            keywords = f"{keywords} 酒店"
        result = await manager.call_tool("Gaode Server", "maps_text_search", keywords=keywords, city=city)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        print(f"[Hotel] 查询失败: {e}")
        return None


# 全局 MCP 管理器实例
_mcp_manager: Optional[MCPToolManager] = None


async def get_mcp_manager() -> MCPToolManager:
    """获取全局 MCP 管理器实例"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPToolManager()
        await _mcp_manager.initialize()
    return _mcp_manager