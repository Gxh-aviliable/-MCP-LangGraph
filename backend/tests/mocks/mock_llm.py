"""Mock LLM 实现

提供 LangChain ChatOpenAI 的 mock 实现，用于测试 Agent 节点
"""
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage


class MockLLM:
    """Mock LangChain ChatOpenAI

    使用方式:
        llm = MockLLM({
            "北京": '{"city": "北京", "ready": true}',
            "工具选择": '{"tool_decisions": {"attraction": true}}'
        })

        response = await llm.ainvoke("我想去北京")
        # response.content = '{"city": "北京", "ready": true}'
    """

    def __init__(self, responses: Dict[str, str] = None):
        """初始化 Mock LLM

        Args:
            responses: 关键词到响应的映射字典
                      当 prompt 包含关键词时，返回对应的响应
        """
        self.responses = responses or {}
        self._default_response = '{"result": "default"}'
        self._call_count = 0
        self._call_history: List[str] = []

    async def ainvoke(self, prompt: Any) -> AIMessage:
        """模拟异步调用

        Args:
            prompt: 输入 prompt（可以是字符串或消息列表）

        Returns:
            AIMessage 对象
        """
        self._call_count += 1

        # 转换 prompt 为字符串
        prompt_str = str(prompt) if not isinstance(prompt, str) else prompt
        self._call_history.append(prompt_str)

        # 根据关键词匹配响应
        for keyword, response in self.responses.items():
            if keyword in prompt_str:
                return AIMessage(content=response)

        return AIMessage(content=self._default_response)

    def with_structured_output(self, schema: Any, method: str = "json_mode"):
        """模拟结构化输出

        返回一个 mock 链，调用 ainvoke 时返回预设的结构化响应
        """
        mock_chain = MagicMock()
        mock_chain.ainvoke = self.ainvoke
        return mock_chain

    def __or__(self, other):
        """支持 | 操作符（用于 prompt | llm 链式调用）"""
        mock_chain = MagicMock()
        mock_chain.ainvoke = self.ainvoke
        return mock_chain

    @property
    def call_count(self) -> int:
        """获取调用次数"""
        return self._call_count

    @property
    def call_history(self) -> List[str]:
        """获取调用历史"""
        return self._call_history.copy()

    def reset(self):
        """重置状态"""
        self._call_count = 0
        self._call_history = []


class MockLLMFactory:
    """Mock LLM 工厂类

    提供常见测试场景的预设 Mock LLM
    """

    @staticmethod
    def create_tool_selector_mock() -> MockLLM:
        """创建用于测试工具选择的 Mock LLM"""
        return MockLLM({
            "工具选择": '{"tool_decisions": {"attraction": true, "weather": true, "transport": true, "hotel": true}, "reason": "标准旅行规划"}',
            "决策": '{"tool_decisions": {"attraction": true, "weather": true, "transport": true, "hotel": true}, "reason": "默认决策"}',
        })

    @staticmethod
    def create_requirement_analyzer_mock() -> MockLLM:
        """创建用于测试需求分析的 Mock LLM"""
        return MockLLM({
            "北京": '{"extracted": {"city": "北京"}, "missing": ["start_date", "end_date"], "ready": false, "suggestions": ["请提供出发日期"]}',
            "上海": '{"extracted": {"city": "上海"}, "missing": ["start_date", "end_date"], "ready": false}',
            "4月": '{"extracted": {"start_date": "2024-04-01"}, "missing": [], "ready": true}',
        })

    @staticmethod
    def create_planner_mock() -> MockLLM:
        """创建用于测试行程规划的 Mock LLM"""
        return MockLLM({
            "规划": '{"city": "北京", "start_date": "2024-04-01", "end_date": "2024-04-03", "days": [{"date": "2024-04-01", "day_index": 0, "description": "第一天行程", "transportation": "地铁", "accommodation": "酒店", "attractions": [{"name": "故宫", "address": "北京市东城区", "location": {"longitude": 116.4, "latitude": 39.9}, "visit_duration": 120, "description": "皇家宫殿", "ticket_price": 60}], "meals": []}]}',
        })


# 预定义的 Mock LLM 实例（用于 conftest.py fixtures）
DEFAULT_MOCK_LLM = MockLLM()
TOOL_SELECTOR_MOCK = MockLLMFactory.create_tool_selector_mock()
REQUIREMENT_ANALYZER_MOCK = MockLLMFactory.create_requirement_analyzer_mock()