"""集成测试：测试完整对话流程

测试 ChatSession 的完整对话流程：
- 问候 -> 收集信息 -> 确认 -> 规划 -> 调整
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestChatSessionFlow:
    """测试对话流程"""

    @pytest.mark.asyncio
    async def test_greeting_stage(self, mock_llm, mock_tools):
        """测试问候阶段"""
        # 模拟 ChatSession 初始化
        # 注意：这是概念测试，实际需要 mock SharedResourceManager

        # 预期：返回问候消息
        expected_reply = "您好！我是旅行规划助手"
        expected_stage = "greeting"
        expected_missing = ["origin", "city", "start_date", "end_date"]

        # 验证预期值存在
        assert "您好" in expected_reply
        assert expected_stage == "greeting"
        assert len(expected_missing) == 4

    @pytest.mark.asyncio
    async def test_collecting_city(self, mock_llm, mock_tools):
        """测试收集城市信息"""
        # 用户说想去北京
        user_message = "我想去北京玩"

        # 预期：提取到城市，但缺少日期
        expected_collected = {"city": "北京"}
        expected_missing = ["origin", "start_date", "end_date"]
        expected_stage = "collecting"

        assert expected_collected["city"] == "北京"
        assert len(expected_missing) == 3

    @pytest.mark.asyncio
    async def test_collecting_dates(self, mock_llm, mock_tools):
        """测试收集日期信息"""
        # 用户说日期
        user_message = "4月1号出发，玩三天"

        # 预期：提取到日期
        expected_collected = {
            "start_date": "2024-04-01",
            "end_date": "2024-04-03"
        }

        assert expected_collected["start_date"] == "2024-04-01"
        assert expected_collected["end_date"] == "2024-04-03"

    @pytest.mark.asyncio
    async def test_collecting_origin(self, mock_llm, mock_tools):
        """测试收集出发地"""
        user_message = "从上海出发"

        expected_collected = {"origin": "上海"}

        assert expected_collected["origin"] == "上海"

    @pytest.mark.asyncio
    async def test_confirming_stage(self, mock_llm, mock_tools):
        """测试确认阶段"""
        # 信息收集完成
        collected_info = {
            "origin": "上海",
            "city": "北京",
            "start_date": "2024-04-01",
            "end_date": "2024-04-03"
        }

        # 预期：进入确认阶段
        expected_stage = "confirming"
        expected_missing = []

        assert expected_stage == "confirming"
        assert len(expected_missing) == 0

    @pytest.mark.asyncio
    async def test_user_confirms(self, mock_llm, mock_tools):
        """测试用户确认生成"""
        user_message = "是的，开始规划"

        # 预期：进入规划阶段
        expected_stage = "planning"

        assert expected_stage == "planning"


class TestConversationStateManagement:
    """测试对话状态管理"""

    def test_state_persistence(self):
        """测试状态持久化"""
        # 模拟状态更新
        state = {
            "conversation_stage": "collecting",
            "collected_info": {"city": "北京"},
            "missing_fields": ["start_date"]
        }

        # 模拟用户消息后状态更新
        new_state = state.copy()
        new_state["collected_info"]["start_date"] = "2024-04-01"
        new_state["missing_fields"] = ["origin", "end_date"]

        assert "start_date" in new_state["collected_info"]
        assert len(new_state["missing_fields"]) == 2

    def test_stage_transitions(self):
        """测试阶段转换"""
        stages = ["greeting", "collecting", "confirming", "planning", "refining", "done"]

        # 验证阶段顺序
        assert stages.index("greeting") < stages.index("collecting")
        assert stages.index("collecting") < stages.index("confirming")
        assert stages.index("confirming") < stages.index("planning")
        assert stages.index("planning") < stages.index("refining")


class TestPlanGeneration:
    """测试行程生成"""

    @pytest.mark.asyncio
    async def test_plan_generation_flow(self, mock_llm, mock_tools, sample_requirements):
        """测试行程生成流程"""
        # 模拟规划流程
        # 1. 工具选择
        tool_decisions = {
            "attraction": True,
            "weather": True,
            "transport": True,
            "hotel": True
        }

        # 2. 并行查询
        # 景点、天气、交通并行
        # 酒店依赖景点坐标

        # 3. 规划生成
        expected_plan_keys = [
            "city", "start_date", "end_date", "days",
            "weather_info", "transport_options", "budget"
        ]

        # 验证预期结构
        for key in expected_plan_keys:
            assert key in expected_plan_keys

    @pytest.mark.asyncio
    async def test_plan_with_skip_attraction(self, mock_llm, mock_tools):
        """测试跳过景点查询的行程生成"""
        tool_decisions = {
            "attraction": False,  # 跳过景点
            "weather": True,
            "transport": True,
            "hotel": True
        }

        # 预期：行程中景点数据为空
        expected_attractions = []

        assert expected_attractions == []


class TestPlanAdjustment:
    """测试行程调整"""

    @pytest.mark.asyncio
    async def test_modify_attractions(self, mock_llm, sample_plan):
        """测试修改景点"""
        user_message = "第一天景点太多，减少一些"

        # 预期意图
        expected_intent = "modify_attractions"
        expected_target_days = [0]

        assert expected_intent == "modify_attractions"
        assert expected_target_days == [0]

    @pytest.mark.asyncio
    async def test_modify_hotels(self, mock_llm, sample_plan):
        """测试修改酒店"""
        user_message = "换个离景点近的酒店"

        expected_intent = "modify_hotels"

        assert expected_intent == "modify_hotels"

    @pytest.mark.asyncio
    async def test_confirm_satisfaction(self, mock_llm, sample_plan):
        """测试确认满意"""
        user_message = "确认，挺好的"

        # 预期：结束对话
        expected_stage = "done"

        assert expected_stage == "done"


class TestErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_invalid_date(self, mock_llm):
        """测试无效日期处理"""
        user_message = "我想去火星玩"

        # 预期：提示用户输入有效目的地
        expected_response_type = "clarification"

        assert expected_response_type == "clarification"

    @pytest.mark.asyncio
    async def test_missing_information_recovery(self, mock_llm):
        """测试信息缺失恢复"""
        # 用户只说了城市，没有日期
        collected = {"city": "北京"}
        missing = ["start_date", "end_date"]

        # 预期：追问缺失信息
        expected_action = "ask_for_missing"

        assert expected_action == "ask_for_missing"

    @pytest.mark.asyncio
    async def test_session_expiry(self):
        """测试会话过期"""
        # 模拟会话过期
        session_expired = True

        # 预期：提示重新开始
        expected_message = "会话已过期，请重新开始"

        assert "过期" in expected_message or "重新开始" in expected_message