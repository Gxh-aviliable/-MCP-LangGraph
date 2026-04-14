"""Test Nodes Extra Functions

测试 nodes.py 中未覆盖的辅助函数：
- parse_detail_result: POI 详情解析
- _all_optional_filled: 可选参数完整性检查
- confirm_check_node: 用户确认检查

这些函数是业务流程的关键支撑。
"""
import pytest
from unittest.mock import AsyncMock
from backend.agent.nodes.nodes import (
    parse_detail_result,
    _all_optional_filled,
)
from backend.model.schemas import WeatherInfo


class TestParseDetailResult:
    """测试 POI 详情解析 - 增强景点/酒店信息"""

    def test_parse_dict_with_direct_fields(self):
        """测试直接包含字段的字典"""
        result = {
            "rating": 4.5,
            "cost": 100,
            "tel": "010-12345678",
            "type": "风景名胜",
            "typecode": "110100"
        }
        detail = parse_detail_result(result)

        assert detail["rating"] == 4.5
        assert detail["cost"] == 100
        assert detail["tel"] == "010-12345678"

    def test_parse_dict_with_pois_wrapper(self):
        """测试包含 pois 包装的结果"""
        result = {
            "pois": [{
                "rating": 4.8,
                "tel": "400-888-8888",
                "type": "旅游景点"
            }]
        }
        detail = parse_detail_result(result)

        assert detail["rating"] == 4.8
        assert detail["tel"] == "400-888-8888"

    def test_parse_json_string(self):
        """测试 JSON 字符串输入"""
        result = '{"rating": 4.2, "cost": 80}'
        detail = parse_detail_result(result)

        assert detail["rating"] == 4.2
        assert detail["cost"] == 80

    def test_parse_with_biz_ext_cost(self):
        """测试 biz_ext 中的 cost 字段"""
        result = {
            "rating": 4.0,
            "biz_ext": {
                "cost": "150元",
                "opening": "08:00-18:00"
            }
        }
        detail = parse_detail_result(result)

        assert detail["cost"] == "150元"
        assert detail["opening_hours"] == "08:00-18:00"

    def test_parse_with_photos(self):
        """测试包含照片的结果"""
        result = {
            "rating": 4.5,
            "photos": [
                {"url": "http://example.com/1.jpg"},
                {"url": "http://example.com/2.jpg"},
                {"url": "http://example.com/3.jpg"},
                {"url": "http://example.com/4.jpg"}  # 第4张应该被截断
            ]
        }
        detail = parse_detail_result(result)

        assert len(detail["photos"]) == 3  # 最多3张

    def test_parse_empty_photos(self):
        """测试空照片列表"""
        result = {
            "rating": 4.0,
            "photos": []
        }
        detail = parse_detail_result(result)

        assert "photos" not in detail  # 空列表应该被过滤

    def test_parse_missing_optional_fields(self):
        """测试缺失可选字段"""
        result = {
            "name": "故宫"  # 只有名称，没有其他字段
        }
        detail = parse_detail_result(result)

        # 应该返回空字典（所有字段都是 None）
        assert detail == {}

    def test_parse_none_value_filtered(self):
        """测试 None 值被过滤"""
        result = {
            "rating": None,
            "cost": None,
            "tel": "12345"
        }
        detail = parse_detail_result(result)

        assert "rating" not in detail
        assert "cost" not in detail
        assert detail["tel"] == "12345"

    def test_parse_invalid_json_string(self):
        """测试无效 JSON 字符串"""
        result = "这不是有效的JSON"
        detail = parse_detail_result(result)

        assert detail == {}

    def test_parse_complex_nested_structure(self):
        """测试复杂嵌套结构"""
        result = {
            "rating": 4.7,
            "cost": "60元",
            "tel": "010-85007421",
            "type": "风景名胜;风景名胜;国家级景点",
            "typecode": "110100",
            "biz_ext": {
                "cost": "60",
                "opening": "08:30-17:00"
            },
            "photos": [
                {"url": "http://photo1.jpg"},
                {"url": "http://photo2.jpg"}
            ]
        }
        detail = parse_detail_result(result)

        assert detail["rating"] == 4.7
        assert detail["tel"] == "010-85007421"
        assert detail["opening_hours"] == "08:30-17:00"
        assert len(detail["photos"]) == 2


class TestAllOptionalFilled:
    """测试可选参数完整性检查"""

    def test_all_filled(self):
        """测试所有可选参数都已填写"""
        collected_info = {
            "interests": ["历史", "美食"],
            "budget_per_day": 500,
            "accommodation_type": "中档",
            "transportation_mode": "火车"
        }
        result = _all_optional_filled(collected_info)

        assert result == True

    def test_missing_interests(self):
        """测试缺失兴趣"""
        collected_info = {
            "budget_per_day": 500,
            "accommodation_type": "中档",
            "transportation_mode": "火车"
        }
        result = _all_optional_filled(collected_info)

        assert result == False

    def test_missing_budget(self):
        """测试缺失预算"""
        collected_info = {
            "interests": ["历史"],
            "accommodation_type": "中档",
            "transportation_mode": "火车"
        }
        result = _all_optional_filled(collected_info)

        assert result == False

    def test_missing_accommodation_type(self):
        """测试缺失住宿类型"""
        collected_info = {
            "interests": ["历史"],
            "budget_per_day": 500,
            "transportation_mode": "火车"
        }
        result = _all_optional_filled(collected_info)

        assert result == False

    def test_missing_transportation_mode(self):
        """测试缺失交通偏好"""
        collected_info = {
            "interests": ["历史"],
            "budget_per_day": 500,
            "accommodation_type": "中档"
        }
        result = _all_optional_filled(collected_info)

        assert result == False

    def test_empty_interests_list(self):
        """测试空兴趣列表"""
        collected_info = {
            "interests": [],  # 空列表
            "budget_per_day": 500,
            "accommodation_type": "中档",
            "transportation_mode": "火车"
        }
        result = _all_optional_filled(collected_info)

        assert result == False

    def test_none_values(self):
        """测试 None 值"""
        collected_info = {
            "interests": ["历史"],
            "budget_per_day": None,  # None 值
            "accommodation_type": "中档",
            "transportation_mode": "火车"
        }
        result = _all_optional_filled(collected_info)

        assert result == False

    def test_empty_string_values(self):
        """测试空字符串值"""
        collected_info = {
            "interests": ["历史"],
            "budget_per_day": 500,
            "accommodation_type": "",  # 空字符串
            "transportation_mode": "火车"
        }
        result = _all_optional_filled(collected_info)

        assert result == False

    def test_empty_dict(self):
        """测试空字典"""
        collected_info = {}
        result = _all_optional_filled(collected_info)

        assert result == False

    def test_partial_fill(self):
        """测试部分填写"""
        collected_info = {
            "interests": ["美食"],
            "budget_per_day": 300
            # 缺少 accommodation_type 和 transportation_mode
        }
        result = _all_optional_filled(collected_info)

        assert result == False


class TestConfirmCheckNode:
    """测试用户确认检查节点"""

    @pytest.mark.asyncio
    async def test_confirm_with_yes(self):
        """测试确认关键词 '是'"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "是"}
        result = await confirm_check_node(state)

        assert result == "confirmed"

    @pytest.mark.asyncio
    async def test_confirm_with_ok(self):
        """测试确认关键词 'ok'"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "ok"}
        result = await confirm_check_node(state)

        assert result == "confirmed"

    @pytest.mark.asyncio
    async def test_confirm_with_confirm(self):
        """测试确认关键词 '确认'"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "确认"}
        result = await confirm_check_node(state)

        assert result == "confirmed"

    @pytest.mark.asyncio
    async def test_confirm_with_good(self):
        """测试确认关键词 '好'"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "好的"}
        result = await confirm_check_node(state)

        assert result == "confirmed"

    @pytest.mark.asyncio
    async def test_confirm_with_can(self):
        """测试确认关键词 '可以'"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "可以"}
        result = await confirm_check_node(state)

        assert result == "confirmed"

    @pytest.mark.asyncio
    async def test_reject_with_no(self):
        """测试拒绝关键词 '不'"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "不行"}
        result = await confirm_check_node(state)

        assert result == "rejected"

    @pytest.mark.asyncio
    async def test_reject_with_cancel(self):
        """测试拒绝关键词 '取消'"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "取消"}
        result = await confirm_check_node(state)

        assert result == "rejected"

    @pytest.mark.asyncio
    async def test_reject_with_wait(self):
        """测试拒绝关键词 '等等'"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "等等"}
        result = await confirm_check_node(state)

        assert result == "rejected"

    @pytest.mark.asyncio
    async def test_pending_with_unclear(self):
        """测试不明确的输入"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "我想调整行程"}
        result = await confirm_check_node(state)

        assert result == "pending"

    @pytest.mark.asyncio
    async def test_pending_with_empty(self):
        """测试空输入"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": ""}
        result = await confirm_check_node(state)

        assert result == "pending"

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        """测试大小写不敏感"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "OK"}
        result = await confirm_check_node(state)

        assert result == "confirmed"

    @pytest.mark.asyncio
    async def test_whitespace_handling(self):
        """测试空格处理"""
        from backend.agent.nodes.nodes import confirm_check_node

        state = {"user_feedback": "  确认  "}
        result = await confirm_check_node(state)

        assert result == "confirmed"


class TestFormatAttractionsEdgeCases:
    """测试景点格式化边界情况"""

    def test_format_with_missing_name(self):
        """测试缺失名称的景点"""
        from backend.agent.nodes.nodes import format_attractions

        attractions = [
            {"description": "这是一个景点"}  # 缺少 name
        ]
        result = format_attractions(attractions)

        assert "未知" in result

    def test_format_with_missing_description(self):
        """测试缺失描述的景点"""
        from backend.agent.nodes.nodes import format_attractions

        attractions = [
            {"name": "故宫"}  # 缺少 description
        ]
        result = format_attractions(attractions)

        assert "故宫" in result


class TestFormatWeatherEdgeCases:
    """测试天气格式化边界情况"""

    def test_format_with_missing_fields(self):
        """测试缺失字段的天气数据"""
        from backend.agent.nodes.nodes import format_weather

        weather = [
            {"date": "2024-04-01"}  # 缺少 day_weather, day_temp
        ]
        result = format_weather(weather)

        assert "2024-04-01" in result
        assert "晴" in result or "未知" in result.lower() or "--" in result

    def test_format_with_none_values(self):
        """测试包含 None 值的天气数据"""
        from backend.agent.nodes.nodes import format_weather

        weather = [
            {
                "date": "2024-04-01",
                "day_weather": None,
                "day_temp": None
            }
        ]
        result = format_weather(weather)

        assert "2024-04-01" in result


class TestSummarizePlanEdgeCases:
    """测试行程摘要边界情况"""

    def test_summarize_with_empty_attractions(self):
        """测试景点为空列表"""
        from backend.agent.nodes.nodes import summarize_plan

        plan = {
            "days": [
                {"day_index": 0, "attractions": []},
                {"day_index": 1, "attractions": []}
            ]
        }
        result = summarize_plan(plan)

        assert "暂无景点" in result

    def test_summarize_with_missing_day_index(self):
        """测试缺失 day_index"""
        from backend.agent.nodes.nodes import summarize_plan

        plan = {
            "days": [
                {"attractions": [{"name": "故宫"}]}  # 缺少 day_index
            ]
        }
        result = summarize_plan(plan)

        # 应该能处理缺失字段
        assert "故宫" in result

    def test_summarize_with_none_plan(self):
        """测试 None 行程"""
        from backend.agent.nodes.nodes import summarize_plan

        result = summarize_plan(None)

        assert result == "暂无行程"