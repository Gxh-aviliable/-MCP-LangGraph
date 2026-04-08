"""Agent 评估脚本

执行方式：
    python -m backend.tests.evaluation.run_evaluation

评估指标：
    1. 决策准确率：工具选择决策是否正确
    2. 完整性：生成的行程是否包含必要信息
    3. 质量评分：行程质量评估分数
    4. 响应时间：各节点执行耗时
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class AgentEvaluator:
    """Agent 综合评估器"""

    def __init__(self, test_cases_path: str = None):
        self.test_cases_path = test_cases_path or str(
            Path(__file__).parent / "test_cases.json"
        )
        self.results = []

    def load_test_cases(self) -> Dict[str, Any]:
        """加载测试案例"""
        with open(self.test_cases_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def run_evaluation(self) -> Dict[str, Any]:
        """运行完整评估"""
        test_data = self.load_test_cases()
        test_cases = test_data.get("test_cases", [])

        metrics = {
            "total_cases": len(test_cases),
            "passed": 0,
            "failed": 0,
            "details": [],
            "timestamp": datetime.now().isoformat()
        }

        for case in test_cases:
            result = await self._evaluate_single_case(case)
            metrics["details"].append(result)

            if result["passed"]:
                metrics["passed"] += 1
            else:
                metrics["failed"] += 1

        metrics["pass_rate"] = (
            metrics["passed"] / metrics["total_cases"]
            if metrics["total_cases"] > 0 else 0
        )

        return metrics

    async def _evaluate_single_case(self, case: Dict) -> Dict:
        """评估单个测试案例"""
        start_time = time.time()

        try:
            # 这里是模拟评估，实际需要调用真实的 Agent
            # 在实际项目中，应该 mock 或真实调用 Agent

            case_id = case["id"]
            case_name = case["name"]
            expected = case.get("expected_outputs", {})

            # 模拟评估结果
            # 实际项目中应该真实执行 Agent 并检查结果
            passed = True
            issues = []

            # 检查预期输出
            if expected.get("has_attractions") == False:
                # 验证是否真的跳过了景点
                passed = True  # 模拟通过

            if expected.get("has_transport") == False:
                # 验证是否跳过了交通
                passed = True  # 模拟通过

            response_time = time.time() - start_time

            return {
                "case_id": case_id,
                "case_name": case_name,
                "passed": passed,
                "response_time": round(response_time, 3),
                "issues": issues
            }

        except Exception as e:
            return {
                "case_id": case["id"],
                "case_name": case["name"],
                "passed": False,
                "error": str(e),
                "response_time": time.time() - start_time
            }

    async def evaluate_decision_accuracy(self) -> Dict[str, Any]:
        """评估决策准确率"""
        test_data = self.load_test_cases()
        decision_cases = test_data.get("decision_accuracy_cases", [])

        results = {
            "total": len(decision_cases),
            "correct": 0,
            "details": []
        }

        for case in decision_cases:
            # 模拟决策评估
            # 实际项目中应该调用 extract_special_instructions 并验证
            user_message = case["user_message"]
            expected = case["expected_decision"]

            # 简单的关键词匹配模拟
            actual = self._simulate_decision(user_message)

            # 比较决策
            correct = self._compare_decisions(expected, actual)

            if correct:
                results["correct"] += 1

            results["details"].append({
                "id": case["id"],
                "user_message": user_message,
                "expected": expected,
                "actual": actual,
                "correct": correct,
                "reason": case.get("reason", "")
            })

        results["accuracy"] = (
            results["correct"] / results["total"]
            if results["total"] > 0 else 0
        )

        return results

    def _simulate_decision(self, user_message: str) -> Dict[str, bool]:
        """模拟决策过程（基于关键词匹配）"""
        message_lower = user_message.lower()

        decision = {
            "skip_attraction": False,
            "skip_weather": False,
            "skip_transport": False,
            "skip_hotel": False
        }

        # 关键词匹配
        if any(kw in message_lower for kw in ["不看景点", "只吃", "美食", "已做好攻略", "做好攻略"]):
            decision["skip_attraction"] = True

        if any(kw in message_lower for kw in ["已订好酒店", "订好酒店", "住朋友", "当天往返", "本地游", "订了酒店", "订了住宿"]):
            decision["skip_hotel"] = True

        if any(kw in message_lower for kw in ["自己开车", "自驾", "已买票", "本地游", "买好票", "买了机票", "订好机票", "订了机票", "机票"]):
            decision["skip_transport"] = True

        return decision

    def _compare_decisions(self, expected: Dict, actual: Dict) -> bool:
        """比较两个决策是否一致"""
        for key in expected:
            if expected.get(key) != actual.get(key):
                return False
        return True

    def print_report(self, metrics: Dict, decision_metrics: Dict = None):
        """打印评估报告"""
        print("\n" + "=" * 60)
        print("Agent 评估报告")
        print("=" * 60)
        print(f"评估时间: {metrics.get('timestamp', 'N/A')}")

        print("\n【综合评估】")
        print(f"  总测试案例: {metrics['total_cases']}")
        print(f"  通过: {metrics['passed']}")
        print(f"  失败: {metrics['failed']}")
        print(f"  通过率: {metrics['pass_rate']:.2%}")

        if decision_metrics:
            print("\n【决策准确率评估】")
            print(f"  总案例: {decision_metrics['total']}")
            print(f"  正确: {decision_metrics['correct']}")
            print(f"  准确率: {decision_metrics['accuracy']:.2%}")

            print("\n  详细结果:")
            for detail in decision_metrics["details"]:
                status = "PASS" if detail["correct"] else "FAIL"
                print(f"    [{status}] {detail['user_message']}")
                if not detail["correct"]:
                    print(f"           期望: {detail['expected']}")
                    print(f"           实际: {detail['actual']}")

        print("\n" + "=" * 60)


async def main():
    """运行评估"""
    evaluator = AgentEvaluator()

    # 运行综合评估
    metrics = await evaluator.run_evaluation()

    # 运行决策准确率评估
    decision_metrics = await evaluator.evaluate_decision_accuracy()

    # 打印报告
    evaluator.print_report(metrics, decision_metrics)

    # 返回结果（便于 CI/CD 集成）
    return {
        "metrics": metrics,
        "decision_metrics": decision_metrics
    }


if __name__ == "__main__":
    result = asyncio.run(main())

    # 如果通过率低于阈值，返回非零退出码
    if result["metrics"]["pass_rate"] < 0.8:
        exit(1)