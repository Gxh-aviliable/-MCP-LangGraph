"""行程评估模块

评估生成的行程质量，支持：
- 完整性检查
- 时间合理性评估
- 路线最优性评估
- 预算准确性评估
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import math


@dataclass
class PlanMetrics:
    """行程评估指标"""

    # 完整性指标 (0-1)
    completeness_score: float = 0.0

    # 合理性指标 (0-1)
    time_efficiency: float = 0.0      # 时间安排合理性
    route_optimality: float = 0.0     # 路线最优性
    budget_accuracy: float = 0.0      # 预算准确性

    # 用户体验指标
    attraction_diversity: float = 0.0   # 景点多样性
    meal_appropriateness: float = 0.0   # 餐饮安排合理性

    # 详细信息
    issues: List[str] = field(default_factory=list)  # 发现的问题
    suggestions: List[str] = field(default_factory=list)  # 改进建议

    # 总分 (0-1)
    overall_score: float = 0.0

    def is_acceptable(self, threshold: float = 0.6) -> bool:
        """判断行程是否可接受"""
        return self.overall_score >= threshold

    def get_summary(self) -> str:
        """获取评估摘要"""
        lines = [
            f"总分: {self.overall_score:.2f}",
            f"- 完整性: {self.completeness_score:.2f}",
            f"- 时间合理性: {self.time_efficiency:.2f}",
            f"- 路线最优性: {self.route_optimality:.2f}",
            f"- 预算准确性: {self.budget_accuracy:.2f}",
        ]

        if self.issues:
            lines.append(f"问题: {', '.join(self.issues)}")

        if self.suggestions:
            lines.append(f"建议: {', '.join(self.suggestions)}")

        return "\n".join(lines)


class PlanEvaluator:
    """行程评估器

    评估生成的行程质量，判断是否需要重新规划

    使用方式:
        evaluator = PlanEvaluator()
        metrics = evaluator.evaluate(plan, requirements)
        should_replan, reason = evaluator.should_replan(metrics)
    """

    # 每天景点数量的合理范围
    MIN_ATTRACTIONS_PER_DAY = 1
    MAX_ATTRACTIONS_PER_DAY = 5
    OPTIMAL_ATTRACTIONS_PER_DAY = (2, 3)

    # 预算偏差容忍度
    BUDGET_TOLERANCE = 0.2  # 20%

    def evaluate(
        self,
        plan: Dict[str, Any],
        requirements: Dict[str, Any]
    ) -> PlanMetrics:
        """评估行程质量

        Args:
            plan: 生成的行程计划
            requirements: 用户需求

        Returns:
            评估指标
        """
        metrics = PlanMetrics()

        if not plan:
            metrics.issues.append("行程为空")
            metrics.overall_score = 0.0
            return metrics

        # 1. 完整性检查
        metrics.completeness_score = self._check_completeness(plan, requirements)

        # 2. 时间合理性检查
        metrics.time_efficiency, time_issues = self._check_time_efficiency(plan)
        metrics.issues.extend(time_issues)

        # 3. 路线最优性检查
        metrics.route_optimality, route_issues = self._check_route_optimality(plan)
        metrics.issues.extend(route_issues)

        # 4. 预算准确性检查
        metrics.budget_accuracy, budget_issues = self._check_budget_accuracy(plan, requirements)
        metrics.issues.extend(budget_issues)

        # 5. 景点多样性检查
        metrics.attraction_diversity = self._check_attraction_diversity(plan)

        # 6. 餐饮安排检查
        metrics.meal_appropriateness = self._check_meal_appropriateness(plan)

        # 计算总分（加权平均）
        weights = {
            'completeness': 0.30,
            'time_efficiency': 0.25,
            'route_optimality': 0.20,
            'budget_accuracy': 0.15,
            'attraction_diversity': 0.05,
            'meal_appropriateness': 0.05,
        }

        metrics.overall_score = (
            metrics.completeness_score * weights['completeness'] +
            metrics.time_efficiency * weights['time_efficiency'] +
            metrics.route_optimality * weights['route_optimality'] +
            metrics.budget_accuracy * weights['budget_accuracy'] +
            metrics.attraction_diversity * weights['attraction_diversity'] +
            metrics.meal_appropriateness * weights['meal_appropriateness']
        )

        # 生成改进建议
        metrics.suggestions = self._generate_suggestions(metrics)

        return metrics

    def should_replan(
        self,
        metrics: PlanMetrics,
        iteration: int = 0
    ) -> Tuple[bool, str]:
        """判断是否需要重新规划

        Args:
            metrics: 评估指标
            iteration: 当前迭代次数

        Returns:
            (是否需要重规划, 原因)
        """
        # 防止无限循环：最多重规划3次
        if iteration >= 3:
            return False, "已达到最大重规划次数"

        # 完整性太低，必须重规划
        if metrics.completeness_score < 0.5:
            return True, "行程信息不完整，需要补充查询"

        # 时间安排严重不合理
        if metrics.time_efficiency < 0.3:
            return True, "时间安排严重不合理，需要重新规划"

        # 总分太低
        if metrics.overall_score < 0.5:
            return True, f"行程质量不达标（得分：{metrics.overall_score:.2f}），需要重新规划"

        return False, "规划质量可接受"

    def _check_completeness(
        self,
        plan: Dict[str, Any],
        requirements: Dict[str, Any]
    ) -> float:
        """检查行程完整性

        检查必要字段是否存在且有效
        """
        required_fields = ['city', 'start_date', 'end_date', 'days']
        optional_fields = ['transport_options', 'weather_info', 'budget', 'hotel']

        # 检查必要字段
        required_present = sum(1 for f in required_fields if plan.get(f))
        required_score = required_present / len(required_fields)

        # 检查可选字段
        optional_present = sum(1 for f in optional_fields if plan.get(f))
        optional_score = optional_present / len(optional_fields)

        # 检查每天的行程是否完整
        days = plan.get('days', [])
        days_complete = 0
        for day in days:
            has_attractions = bool(day.get('attractions'))
            has_meals = bool(day.get('meals'))
            if has_attractions or has_meals:
                days_complete += 1

        days_score = days_complete / len(days) if days else 0

        # 综合评分
        score = required_score * 0.5 + optional_score * 0.2 + days_score * 0.3

        return min(1.0, score)

    def _check_time_efficiency(
        self,
        plan: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """检查时间安排合理性

        检查每天景点数量是否合理
        """
        issues = []
        days = plan.get('days', [])

        if not days:
            return 0.0, ["没有每日行程"]

        scores = []
        for i, day in enumerate(days):
            attractions = day.get('attractions', [])
            num_attractions = len(attractions)

            if num_attractions < self.MIN_ATTRACTIONS_PER_DAY:
                scores.append(0.5)
                issues.append(f"第{i+1}天景点太少({num_attractions}个)")
            elif num_attractions > self.MAX_ATTRACTIONS_PER_DAY:
                scores.append(0.4)
                issues.append(f"第{i+1}天景点太多({num_attractions}个)，行程可能太紧")
            elif self.OPTIMAL_ATTRACTIONS_PER_DAY[0] <= num_attractions <= self.OPTIMAL_ATTRACTIONS_PER_DAY[1]:
                scores.append(1.0)  # 最佳
            else:
                scores.append(0.8)  # 可接受

        avg_score = sum(scores) / len(scores) if scores else 0
        return avg_score, issues

    def _check_route_optimality(
        self,
        plan: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """检查路线最优性

        简化版本：检查景点是否有位置信息
        完整版本需要计算实际距离
        """
        issues = []
        days = plan.get('days', [])

        if not days:
            return 0.5, []

        total_attractions = 0
        with_location = 0

        for day in days:
            for attr in day.get('attractions', []):
                total_attractions += 1
                if attr.get('location'):
                    with_location += 1

        # 简化：有位置信息的景点比例作为评分
        score = with_location / total_attractions if total_attractions > 0 else 0.5

        if score < 0.5:
            issues.append("部分景点缺少位置信息，可能影响路线规划")

        return score, issues

    def _check_budget_accuracy(
        self,
        plan: Dict[str, Any],
        requirements: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """检查预算准确性

        对比计算预算和用户预算
        """
        issues = []

        # 获取用户预算
        user_budget = requirements.get('budget_per_day')
        if not user_budget:
            return 0.7, []  # 没有用户预算，默认可接受

        # 获取行程预算
        plan_budget = plan.get('budget', {})
        if not plan_budget:
            return 0.5, ["行程缺少预算信息"]

        # 计算每日预算
        days = plan.get('days', [])
        num_days = len(days) if days else 1

        total_budget = plan_budget.get('total', 0)
        daily_budget = total_budget / num_days if num_days > 0 else 0

        if daily_budget == 0:
            return 0.5, ["预算信息不完整"]

        # 计算偏差
        deviation = abs(daily_budget - user_budget) / user_budget

        if deviation > self.BUDGET_TOLERANCE:
            issues.append(f"预算偏差较大：用户预算{user_budget}元/天，行程预算{daily_budget:.0f}元/天")

        # 偏差越小，分数越高
        score = max(0, 1 - deviation)
        return score, issues

    def _check_attraction_diversity(self, plan: Dict[str, Any]) -> float:
        """检查景点多样性

        检查是否有重复景点
        """
        days = plan.get('days', [])
        if not days:
            return 0.5

        all_names = []
        for day in days:
            for attr in day.get('attractions', []):
                name = attr.get('name', '')
                if name:
                    all_names.append(name)

        if not all_names:
            return 0.5

        # 检查重复
        unique_names = set(all_names)
        if len(unique_names) < len(all_names):
            return 0.6  # 有重复

        return 1.0  # 无重复

    def _check_meal_appropriateness(self, plan: Dict[str, Any]) -> float:
        """检查餐饮安排合理性

        检查每天是否有三餐
        """
        days = plan.get('days', [])
        if not days:
            return 0.5

        scores = []
        for day in days:
            meals = day.get('meals', [])
            meal_types = set(m.get('type') for m in meals)

            # 理想情况下应该有三餐
            expected_meals = {'breakfast', 'lunch', 'dinner'}
            coverage = len(meal_types & expected_meals) / 3
            scores.append(coverage)

        return sum(scores) / len(scores) if scores else 0.5

    def _generate_suggestions(self, metrics: PlanMetrics) -> List[str]:
        """根据评估结果生成改进建议"""
        suggestions = []

        if metrics.completeness_score < 0.7:
            suggestions.append("补充缺失的行程信息（如交通、天气、预算）")

        if metrics.time_efficiency < 0.6:
            suggestions.append("调整每天的景点数量，避免行程过紧或过松")

        if metrics.route_optimality < 0.6:
            suggestions.append("优化游览路线，减少不必要的往返")

        if metrics.budget_accuracy < 0.6:
            suggestions.append("调整预算分配，使其更符合用户预期")

        if metrics.attraction_diversity < 0.7:
            suggestions.append("避免安排重复景点")

        if metrics.meal_appropriateness < 0.7:
            suggestions.append("完善每日餐饮安排")

        return suggestions


# 便捷函数
def evaluate_plan(
    plan: Dict[str, Any],
    requirements: Dict[str, Any]
) -> PlanMetrics:
    """评估行程质量"""
    evaluator = PlanEvaluator()
    return evaluator.evaluate(plan, requirements)


def should_replan(
    metrics: PlanMetrics,
    iteration: int = 0
) -> Tuple[bool, str]:
    """判断是否需要重新规划"""
    evaluator = PlanEvaluator()
    return evaluator.should_replan(metrics, iteration)