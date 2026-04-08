"""测试行程评估器

测试 PlanEvaluator 的各项评估功能：
- 完整性检查
- 时间合理性评估
- 路线最优性评估
- 预算准确性评估
"""
import pytest
from backend.evaluation.evaluator import (
    PlanEvaluator,
    PlanMetrics,
    evaluate_plan,
    should_replan,
)


class TestPlanMetrics:
    """测试评估指标数据类"""

    def test_default_values(self):
        """测试默认值"""
        metrics = PlanMetrics()
        assert metrics.overall_score == 0.0
        assert metrics.completeness_score == 0.0
        assert metrics.issues == []
        assert metrics.suggestions == []

    def test_is_acceptable(self):
        """测试可接受判断"""
        metrics = PlanMetrics(overall_score=0.7)
        assert metrics.is_acceptable() == True

        metrics = PlanMetrics(overall_score=0.5)
        assert metrics.is_acceptable() == False

    def test_is_acceptable_custom_threshold(self):
        """测试自定义阈值"""
        metrics = PlanMetrics(overall_score=0.65)
        assert metrics.is_acceptable(0.6) == True
        assert metrics.is_acceptable(0.7) == False

    def test_get_summary(self):
        """测试摘要生成"""
        metrics = PlanMetrics(
            overall_score=0.75,
            completeness_score=0.8,
            time_efficiency=0.7,
            issues=["测试问题"],
            suggestions=["测试建议"]
        )
        summary = metrics.get_summary()
        assert "总分" in summary
        assert "0.75" in summary
        assert "测试问题" in summary
        assert "测试建议" in summary


class TestPlanEvaluatorCompleteness:
    """测试完整性检查"""

    def test_empty_plan(self):
        """测试空行程"""
        evaluator = PlanEvaluator()
        metrics = evaluator.evaluate(None, {})
        assert metrics.overall_score == 0.0
        assert "行程为空" in metrics.issues

    def test_minimal_plan(self):
        """测试最小行程"""
        evaluator = PlanEvaluator()
        plan = {
            "city": "北京",
            "start_date": "2024-04-01",
            "end_date": "2024-04-03",
            "days": [
                {"attractions": [{"name": "故宫"}], "meals": []}
            ]
        }
        metrics = evaluator.evaluate(plan, {})
        assert metrics.completeness_score > 0

    def test_complete_plan(self, sample_plan):
        """测试完整行程"""
        evaluator = PlanEvaluator()
        metrics = evaluator.evaluate(sample_plan, {})
        assert metrics.completeness_score > 0.5

    def test_missing_required_fields(self):
        """测试缺少必要字段"""
        evaluator = PlanEvaluator()
        plan = {
            "city": "北京",
            # 缺少 start_date, end_date, days
        }
        metrics = evaluator.evaluate(plan, {})
        assert metrics.completeness_score < 0.5


class TestPlanEvaluatorTimeEfficiency:
    """测试时间合理性检查"""

    def test_optimal_attractions_per_day(self):
        """测试最佳景点数量（2-3个）"""
        evaluator = PlanEvaluator()
        plan = {
            "city": "北京",
            "start_date": "2024-04-01",
            "end_date": "2024-04-01",
            "days": [
                {
                    "attractions": [
                        {"name": "故宫"},
                        {"name": "天安门"}
                    ]
                }
            ]
        }
        score, issues = evaluator._check_time_efficiency(plan)
        assert score == 1.0  # 2个景点是最佳
        assert len(issues) == 0

    def test_too_many_attractions(self):
        """测试景点太多"""
        evaluator = PlanEvaluator()
        plan = {
            "days": [
                {
                    "attractions": [
                        {"name": f"景点{i}"} for i in range(6)
                    ]
                }
            ]
        }
        score, issues = evaluator._check_time_efficiency(plan)
        assert score < 1.0
        assert any("太多" in issue for issue in issues)

    def test_too_few_attractions(self):
        """测试景点太少"""
        evaluator = PlanEvaluator()
        plan = {
            "days": [
                {"attractions": []}
            ]
        }
        score, issues = evaluator._check_time_efficiency(plan)
        assert score < 1.0


class TestPlanEvaluatorRouteOptimality:
    """测试路线最优性检查"""

    def test_attractions_with_location(self):
        """测试有位置信息的景点"""
        evaluator = PlanEvaluator()
        plan = {
            "days": [
                {
                    "attractions": [
                        {"name": "故宫", "location": {"longitude": 116.4, "latitude": 39.9}},
                        {"name": "天安门", "location": {"longitude": 116.39, "latitude": 39.9}}
                    ]
                }
            ]
        }
        score, issues = evaluator._check_route_optimality(plan)
        assert score == 1.0

    def test_attractions_without_location(self):
        """测试没有位置信息的景点"""
        evaluator = PlanEvaluator()
        plan = {
            "days": [
                {
                    "attractions": [
                        {"name": "故宫"},
                        {"name": "天安门"}
                    ]
                }
            ]
        }
        score, issues = evaluator._check_route_optimality(plan)
        assert score < 0.5


class TestPlanEvaluatorBudget:
    """测试预算准确性检查"""

    def test_no_user_budget(self):
        """测试没有用户预算"""
        evaluator = PlanEvaluator()
        plan = {"budget": {"total": 1000}}
        score, issues = evaluator._check_budget_accuracy(plan, {})
        assert score == 0.7  # 默认分数

    def test_budget_within_tolerance(self):
        """测试预算在容忍范围内"""
        evaluator = PlanEvaluator()
        plan = {
            "days": [{"attractions": []}, {"attractions": []}, {"attractions": []}],  # 3天
            "budget": {"total": 1500}  # 3天，每天500，与用户预算匹配
        }
        requirements = {"budget_per_day": 500}
        score, issues = evaluator._check_budget_accuracy(plan, requirements)
        assert score > 0.8

    def test_budget_exceeds_tolerance(self):
        """测试预算超出容忍范围"""
        evaluator = PlanEvaluator()
        plan = {
            "days": [{"attractions": []}, {"attractions": []}, {"attractions": []}],
            "budget": {"total": 3000}  # 3天，每天1000，远超用户预算
        }
        requirements = {"budget_per_day": 300}
        score, issues = evaluator._check_budget_accuracy(plan, requirements)
        assert score < 0.5
        assert any("偏差" in issue for issue in issues)


class TestPlanEvaluatorShouldReplan:
    """测试重规划决策"""

    def test_max_iterations_reached(self):
        """测试达到最大迭代次数"""
        evaluator = PlanEvaluator()
        metrics = PlanMetrics(overall_score=0.3)
        should, reason = evaluator.should_replan(metrics, iteration=3)
        assert should == False
        assert "最大重规划次数" in reason

    def test_low_completeness(self):
        """测试完整性太低"""
        evaluator = PlanEvaluator()
        metrics = PlanMetrics(completeness_score=0.3, overall_score=0.5)
        should, reason = evaluator.should_replan(metrics, iteration=0)
        assert should == True
        assert "不完整" in reason

    def test_low_time_efficiency(self):
        """测试时间安排不合理"""
        evaluator = PlanEvaluator()
        metrics = PlanMetrics(
            completeness_score=0.8,
            time_efficiency=0.2,
            overall_score=0.4
        )
        should, reason = evaluator.should_replan(metrics, iteration=0)
        assert should == True
        assert "时间安排" in reason

    def test_acceptable_quality(self):
        """测试质量可接受"""
        evaluator = PlanEvaluator()
        metrics = PlanMetrics(
            completeness_score=0.8,
            time_efficiency=0.7,
            overall_score=0.75
        )
        should, reason = evaluator.should_replan(metrics, iteration=0)
        assert should == False


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_evaluate_plan_function(self, sample_plan, sample_requirements):
        """测试 evaluate_plan 函数"""
        metrics = evaluate_plan(sample_plan, sample_requirements)
        assert isinstance(metrics, PlanMetrics)
        assert metrics.overall_score > 0

    def test_should_replan_function(self):
        """测试 should_replan 函数"""
        metrics = PlanMetrics(overall_score=0.3)
        result = should_replan(metrics, iteration=0)
        assert isinstance(result, tuple)
        assert len(result) == 2