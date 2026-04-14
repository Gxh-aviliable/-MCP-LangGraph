"""pytest 共享配置和 fixtures

提供测试所需的共享 fixtures，包括：
- Mock LLM
- Mock MCP 工具
- 测试数据
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.tests.mocks.mock_llm import MockLLM, MockLLMFactory
from backend.tests.mocks.mock_mcp_tools import create_mock_tools, MOCK_TOOLS


# ==================== LLM Fixtures ====================

@pytest.fixture
def mock_llm():
    """提供基础的 Mock LLM"""
    return MockLLM()


@pytest.fixture
def tool_selector_mock():
    """提供用于工具选择测试的 Mock LLM"""
    return MockLLMFactory.create_tool_selector_mock()


@pytest.fixture
def requirement_analyzer_mock():
    """提供用于需求分析测试的 Mock LLM"""
    return MockLLMFactory.create_requirement_analyzer_mock()


@pytest.fixture
def planner_mock():
    """提供用于规划测试的 Mock LLM"""
    return MockLLMFactory.create_planner_mock()


# ==================== MCP Tools Fixtures ====================

@pytest.fixture
def mock_tools():
    """提供 Mock MCP 工具列表"""
    return MOCK_TOOLS


@pytest.fixture
def mock_attraction_tool():
    """提供单独的景点搜索工具"""
    for tool in MOCK_TOOLS:
        if tool.name == "maps_text_search":
            return tool
    return None


@pytest.fixture
def mock_weather_tool():
    """提供单独的天气查询工具"""
    for tool in MOCK_TOOLS:
        if tool.name == "maps_weather":
            return tool
    return None


# ==================== 测试数据 Fixtures ====================

@pytest.fixture
def sample_state():
    """提供测试用的 Agent 状态"""
    return {
        "city": "北京",
        "origin": "上海",
        "start_date": "2024-04-01",
        "end_date": "2024-04-03",
        "interests": ["历史古迹"],
        "budget_per_day": 500,
        "accommodation_type": "中档",
        "attractions_data": [],
        "weather_data": [],
        "hotels_data": [],
        "transport_data": [],
        "messages": [],
        "user_feedback": "",
        "conversation_stage": "collecting",
        "collected_info": {},
        "missing_fields": ["origin", "city", "start_date", "end_date"],
        "ready_to_plan": False,
        "tool_decisions": None,
        "special_instructions": None,
        "final_plan": None,
    }


@pytest.fixture
def sample_plan():
    """提供测试用的行程计划"""
    return {
        "city": "北京",
        "start_date": "2024-04-01",
        "end_date": "2024-04-03",
        "days": [
            {
                "date": "2024-04-01",
                "day_index": 0,
                "description": "第一天：故宫和天安门",
                "transportation": "地铁",
                "accommodation": "酒店",
                "hotel": {"name": "北京饭店", "address": "北京市东城区", "rating": 4.5},
                "attractions": [
                    {"name": "故宫", "address": "北京市东城区", "visit_duration": 180, "ticket_price": 60},
                    {"name": "天安门", "address": "北京市东城区", "visit_duration": 60, "ticket_price": 0}
                ],
                "meals": [
                    {"type": "breakfast", "name": "酒店早餐", "estimated_cost": 50},
                    {"type": "lunch", "name": "故宫附近餐厅", "estimated_cost": 80},
                    {"type": "dinner", "name": "王府井小吃街", "estimated_cost": 100}
                ]
            },
            {
                "date": "2024-04-02",
                "day_index": 1,
                "description": "第二天：长城",
                "transportation": "大巴",
                "accommodation": "酒店",
                "attractions": [
                    {"name": "八达岭长城", "address": "北京市延庆区", "visit_duration": 300, "ticket_price": 40}
                ],
                "meals": []
            },
            {
                "date": "2024-04-03",
                "day_index": 2,
                "description": "第三天：颐和园",
                "transportation": "地铁",
                "accommodation": "",
                "attractions": [
                    {"name": "颐和园", "address": "北京市海淀区", "visit_duration": 180, "ticket_price": 30}
                ],
                "meals": []
            }
        ],
        "weather_info": [
            {"date": "2024-04-01", "day_weather": "晴", "day_temp": 16, "night_temp": 8},
            {"date": "2024-04-02", "day_weather": "多云", "day_temp": 18, "night_temp": 10},
            {"date": "2024-04-03", "day_weather": "晴", "day_temp": 20, "night_temp": 12}
        ],
        "budget": {
            "transport": 1106,
            "total_attractions": 130,
            "total_hotels": 1600,
            "total_meals": 230,
            "total": 3066
        }
    }


@pytest.fixture
def sample_requirements():
    """提供测试用的用户需求"""
    return {
        "origin": "上海",
        "city": "北京",
        "start_date": "2024-04-01",
        "end_date": "2024-04-03",
        "interests": ["历史古迹"],
        "budget_per_day": 500
    }


# ==================== 时间 Fixtures ====================

@pytest.fixture
def fixed_date():
    """提供固定的测试日期（2024-04-01）"""
    return datetime(2024, 4, 1)


@pytest.fixture
def frozen_time(fixed_date):
    """冻结时间的 fixture"""
    from unittest.mock import patch
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = fixed_date
        yield mock_datetime


# ==================== Pytest 配置 ====================

def pytest_configure(config):
    """pytest 配置钩子"""
    # 注册自定义标记
    config.addinivalue_line("markers", "unit: 单元测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "slow: 慢速测试")


def pytest_collection_modifyitems(config, items):
    """根据标记修改测试项"""
    # 为没有标记的测试添加 unit 标记
    for item in items:
        if not list(item.iter_markers()):
            item.add_marker(pytest.mark.unit)