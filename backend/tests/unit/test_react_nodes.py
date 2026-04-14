"""Test ReAct Agent Core Functions

测试 ReAct Agent 核心节点的辅助函数：
- _parse_json_response: JSON 解析
- _build_reasoning_context: 构建推理上下文
- _format_available_actions: 格式化可用行动
- _generate_observation: 生成观察结果
- _format_thoughts_summary: 格式化思考链摘要

这些是 Agent 智能决策的核心支撑函数。
"""
import pytest
from backend.agent.nodes.react_nodes import (
    _parse_json_response,
    _build_reasoning_context,
    _format_available_actions,
    _generate_observation,
    _format_thoughts_summary,
    ACTIONS,
)


class TestParseJsonResponse:
    """测试 JSON 解析函数 - Agent 与 LLM 交互的核心"""

    def test_parse_valid_json_object(self):
        """测试解析有效的 JSON 对象"""
        content = '{"thought": "需要查询景点", "action": "query_attraction", "confidence": 0.8}'
        result = _parse_json_response(content)

        assert result["thought"] == "需要查询景点"
        assert result["action"] == "query_attraction"
        assert result["confidence"] == 0.8

    def test_parse_json_in_markdown_block(self):
        """测试解析 Markdown 代码块中的 JSON"""
        content = '''这是我的决策：
```json
{"thought": "分析中", "action": "generate_plan"}
```
'''
        result = _parse_json_response(content)

        assert result["thought"] == "分析中"
        assert result["action"] == "generate_plan"

    def test_parse_json_array(self):
        """测试解析 JSON 数组（某些场景 LLM 返回数组）"""
        content = '[{"name": "故宫"}, {"name": "天安门"}]'
        result = _parse_json_response(content)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "故宫"

    def test_parse_nested_json(self):
        """测试解析嵌套 JSON"""
        content = '{"data": {"inner": "value"}, "count": 5}'
        result = _parse_json_response(content)

        assert result["data"]["inner"] == "value"
        assert result["count"] == 5

    def test_parse_malformed_json_returns_empty_dict(self):
        """测试解析格式错误的 JSON 返回空字典"""
        content = '这不是 JSON'
        result = _parse_json_response(content)

        assert result == {}

    def test_parse_empty_string_returns_empty_dict(self):
        """测试空字符串返回空字典"""
        result = _parse_json_response("")

        assert result == {}

    def test_parse_incomplete_json_returns_empty_dict(self):
        """测试不完整的 JSON 返回空字典"""
        content = '{"thought": "测试"'  # 缺少闭合括号
        result = _parse_json_response(content)

        assert result == {}

    def test_parse_json_with_extra_text(self):
        """测试包含额外文本的 JSON"""
        content = '让我分析一下：{"action": "finish", "should_continue": false} 这是我决定'
        result = _parse_json_response(content)

        assert result["action"] == "finish"
        assert result["should_continue"] == False

    def test_parse_multiline_json(self):
        """测试多行 JSON"""
        content = '''{
            "thought": "多行分析",
            "action": "query_weather",
            "confidence": 0.9
        }'''
        result = _parse_json_response(content)

        assert result["thought"] == "多行分析"
        assert result["confidence"] == 0.9


class TestBuildReasoningContext:
    """测试构建推理上下文 - Agent 决策的依据"""

    def test_basic_context(self):
        """测试基本上下文构建"""
        state = {
            "city": "北京",
            "origin": "上海",
            "start_date": "2024-04-01",
            "end_date": "2024-04-03",
            "interests": ["历史古迹", "美食"],
            "attractions_data": [{"name": "故宫"}],
            "weather_data": [{"date": "2024-04-01"}],
            "hotels_data": [{"name": "北京饭店"}],
            "transport_data": [],
            "iteration_count": 1,
        }
        context = _build_reasoning_context(state)

        assert "北京" in context
        assert "上海" in context
        assert "2024-04-01" in context
        assert "历史古迹" in context
        assert "景点: 1 个" in context
        assert "天气: 1 条" in context
        assert "酒店: 1 家" in context

    def test_context_with_missing_fields(self):
        """测试缺失字段时的上下文"""
        state = {
            "city": "杭州",
            "origin": "",
            "start_date": "",
            "end_date": "",
            "interests": [],
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "transport_data": [],
            "iteration_count": 0,
        }
        context = _build_reasoning_context(state)

        assert "杭州" in context
        # 空字段可能显示为空或"未指定"
        assert "景点: 0 个" in context
        assert "行程: 未生成" in context

    def test_context_with_special_instructions(self):
        """测试包含特殊说明的上下文"""
        state = {
            "city": "北京",
            "origin": "上海",
            "start_date": "2024-04-01",
            "end_date": "2024-04-03",
            "interests": [],
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "transport_data": [],
            "iteration_count": 0,
            "special_instructions": {
                "skip_attraction": True,
                "skip_attraction_reason": "用户已做好攻略"
            }
        }
        context = _build_reasoning_context(state)

        assert "跳过" in context or "attraction" in context.lower()

    def test_context_with_user_feedback(self):
        """测试包含用户反馈的上下文"""
        state = {
            "city": "北京",
            "origin": "上海",
            "start_date": "2024-04-01",
            "end_date": "2024-04-03",
            "interests": [],
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "transport_data": [],
            "iteration_count": 0,
            "user_feedback": "第一天景点太多了",
            "adjustment_request": True,
        }
        context = _build_reasoning_context(state)

        assert "用户反馈" in context or "第一天景点太多" in context

    def test_context_shows_plan_status(self):
        """测试上下文显示行程状态"""
        state_no_plan = {
            "city": "北京",
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "transport_data": [],
            "iteration_count": 0,
        }
        context = _build_reasoning_context(state_no_plan)
        assert "未生成" in context

        state_with_plan = {
            "city": "北京",
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "transport_data": [],
            "iteration_count": 1,
            "final_plan": {"city": "北京"}
        }
        context = _build_reasoning_context(state_with_plan)
        assert "已生成" in context


class TestFormatAvailableActions:
    """测试格式化可用行动列表"""

    def test_format_returns_string(self):
        """测试返回字符串格式"""
        result = _format_available_actions()

        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_contains_all_actions(self):
        """测试包含所有定义的行动"""
        result = _format_available_actions()

        for action_name in ACTIONS.keys():
            assert action_name in result

    def test_format_contains_descriptions(self):
        """测试包含行动描述"""
        result = _format_available_actions()

        # 检查一些关键描述
        assert "查询景点" in result or "attraction" in result.lower()
        assert "生成行程" in result or "generate_plan" in result

    def test_format_contains_conditions(self):
        """测试包含执行条件"""
        result = _format_available_actions()

        assert "条件" in result or "condition" in result.lower()


class TestGenerateObservation:
    """测试生成观察结果 - Agent 感知环境的核心"""

    def test_observation_query_attraction(self):
        """测试景点查询观察"""
        state = {"attractions_data": [{"name": "故宫"}, {"name": "天安门"}]}
        result = _generate_observation("query_attraction", state)

        assert "2" in result
        assert "景点" in result

    def test_observation_query_weather(self):
        """测试天气查询观察"""
        state = {"weather_data": [{"date": "2024-04-01"}, {"date": "2024-04-02"}]}
        result = _generate_observation("query_weather", state)

        assert "2" in result
        assert "天气" in result

    def test_observation_query_hotel(self):
        """测试酒店查询观察"""
        state = {"hotels_data": [{"name": "酒店1"}, {"name": "酒店2"}, {"name": "酒店3"}]}
        result = _generate_observation("query_hotel", state)

        assert "3" in result
        assert "酒店" in result

    def test_observation_query_transport(self):
        """测试交通查询观察"""
        state = {"transport_data": [{"name": "G1"}]}
        result = _generate_observation("query_transport", state)

        assert "1" in result
        assert "交通" in result

    def test_observation_generate_plan_success(self):
        """测试行程生成成功观察"""
        state = {"final_plan": {"city": "北京"}}
        result = _generate_observation("generate_plan", state)

        assert "生成" in result

    def test_observation_generate_plan_failure(self):
        """测试行程生成失败观察"""
        state = {}
        result = _generate_observation("generate_plan", state)

        assert "失败" in result or "未生成" in result

    def test_observation_evaluate_plan(self):
        """测试行程评估观察"""
        state = {"plan_metrics": {"overall_score": 0.75}}
        result = _generate_observation("evaluate_plan", state)

        assert "0.75" in result

    def test_observation_finish(self):
        """测试完成行动观察"""
        result = _generate_observation("finish", {})

        assert "结束" in result or "完成" in result

    def test_observation_unknown_action(self):
        """测试未知行动观察"""
        result = _generate_observation("unknown_action", {})

        assert "完成" in result  # 默认返回


class TestFormatThoughtsSummary:
    """测试格式化思考链摘要"""

    def test_empty_thoughts(self):
        """测试空思考链"""
        result = _format_thoughts_summary([])

        assert "暂无" in result or result == "暂无思考记录"

    def test_single_thought(self):
        """测试单条思考"""
        thoughts = [
            {
                "step": 1,
                "action": "query_attraction",
                "observation": "查询到5个景点"
            }
        ]
        result = _format_thoughts_summary(thoughts)

        assert "Step 1" in result
        assert "query_attraction" in result

    def test_multiple_thoughts(self):
        """测试多条思考"""
        thoughts = [
            {"step": 1, "action": "query_attraction", "observation": "查询到景点"},
            {"step": 2, "action": "query_weather", "observation": "查询到天气"},
            {"step": 3, "action": "generate_plan", "observation": "生成行程"},
        ]
        result = _format_thoughts_summary(thoughts)

        assert "Step 1" in result
        assert "Step 2" in result
        assert "Step 3" in result

    def test_thoughts_truncated_to_recent(self):
        """测试只显示最近5条思考"""
        thoughts = [
            {"step": i, "action": f"action_{i}", "observation": f"obs_{i}"}
            for i in range(1, 11)  # 10 条
        ]
        result = _format_thoughts_summary(thoughts)

        # 应该包含最近的步骤
        assert "Step 6" in result
        assert "Step 10" in result
        # 早期步骤可能被截断（取决于实现）

    def test_thought_with_missing_fields(self):
        """测试缺失字段的思考"""
        thoughts = [
            {"step": 1}  # 缺少 action 和 observation
        ]
        result = _format_thoughts_summary(thoughts)

        # 应该能处理缺失字段
        assert "Step 1" in result


class TestActionsDefinition:
    """测试行动定义常量"""

    def test_actions_has_required_keys(self):
        """测试行动定义包含必要字段"""
        required_actions = [
            "query_attraction",
            "query_weather",
            "query_hotel",
            "query_transport",
            "generate_plan",
            "evaluate_plan",
            "refine_plan",
            "adjust_plan",
            "finish"
        ]

        for action in required_actions:
            assert action in ACTIONS, f"Missing action: {action}"

    def test_actions_have_descriptions(self):
        """测试每个行动都有描述"""
        for action_name, action_info in ACTIONS.items():
            assert "description" in action_info, f"Missing description for {action_name}"
            assert len(action_info["description"]) > 0

    def test_actions_have_conditions(self):
        """测试每个行动都有条件"""
        for action_name, action_info in ACTIONS.items():
            assert "condition" in action_info, f"Missing condition for {action_name}"

    def test_finish_action_has_no_tool(self):
        """测试 finish 行动不需要工具"""
        assert ACTIONS["finish"]["tool"] is None