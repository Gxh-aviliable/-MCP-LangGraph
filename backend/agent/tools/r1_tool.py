"""DeepSeek R1 深度分析工具

用于复杂场景的深度推理：
- 多目的地路线优化
- 预算优化
- 复杂约束分析
"""
from openai import AsyncOpenAI
import json
from typing import Dict, Any, Optional

from backend.config.settings import settings


class DeepSeekR1Analyzer:
    """DeepSeek R1 深度分析器

    用于处理需要深度推理的复杂旅行规划场景：
    - 多目的地路线优化
    - 预算紧张时的优化
    - 特殊需求（老人/儿童）的行程调整
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com"
    ):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or settings.deepseek_api_key
        )
        self.model = settings.reasoning_model
        self.temperature = 0.7

    async def analyze(
        self,
        problem: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """深度分析复杂问题

        Args:
            problem: 需要分析的问题描述
            context: 上下文信息（已收集的旅行信息等）

        Returns:
            分析结果（JSON格式）
        """
        prompt = self._build_analysis_prompt(problem, context)

        try:
            print(f"[R1] 开始深度分析...")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=4000
            )

            result = response.choices[0].message.content
            print(f"[R1] 分析完成，返回 {len(result)} 字符")
            return result

        except Exception as e:
            print(f"[R1] 分析失败: {e}")
            error_result = {
                "analysis": f"分析失败: {str(e)}",
                "constraints": [],
                "suggestions": [],
                "reasoning": "无法完成深度分析"
            }
            return json.dumps(error_result, ensure_ascii=False)

    async def optimize_route(
        self,
        destinations: list,
        origin: str,
        budget: float,
        days: int,
        special_needs: Optional[list] = None
    ) -> Dict[str, Any]:
        """优化旅行路线

        Args:
            destinations: 目的地列表
            origin: 出发地
            budget: 预算
            days: 天数
            special_needs: 特殊需求（如老人、儿童）

        Returns:
            优化后的路线规划
        """
        problem = f"""
请优化以下旅行路线：
- 出发地: {origin}
- 目的地清单: {', '.join(destinations)}
- 预算限制: {budget}元
- 时间限制: {days}天
- 特殊需求: {special_needs or '无'}

要求：
1. 给出最优的游览顺序
2. 每个地点的合理停留时间
3. 交通方式建议
4. 预算分配建议
"""

        context = {
            "destinations": destinations,
            "origin": origin,
            "budget": budget,
            "days": days,
            "special_needs": special_needs
        }

        result = await self.analyze(problem, context)

        try:
            # 尝试解析JSON
            if result.strip().startswith('{'):
                return json.loads(result)
            return {"raw_response": result}
        except json.JSONDecodeError:
            return {"raw_response": result}

    async def analyze_budget(
        self,
        total_budget: float,
        days: int,
        num_people: int,
        destinations: list,
        preferences: Optional[list] = None
    ) -> Dict[str, Any]:
        """预算分析与优化

        Args:
            total_budget: 总预算
            days: 天数
            num_people: 人数
            destinations: 目的地列表
            preferences: 偏好

        Returns:
            预算分配建议
        """
        per_day = total_budget / days
        per_person = total_budget / num_people

        problem = f"""
请分析以下旅行预算并给出优化建议：
- 总预算: {total_budget}元
- 天数: {days}天 (日均{per_day:.0f}元)
- 人数: {num_people}人 (人均{per_person:.0f}元)
- 目的地: {', '.join(destinations)}
- 偏好: {preferences or '无特殊偏好'}

请提供：
1. 交通、住宿、餐饮、门票的预算分配比例
2. 省钱建议
3. 是否需要增加预算
"""

        context = {
            "total_budget": total_budget,
            "days": days,
            "num_people": num_people,
            "destinations": destinations
        }

        result = await self.analyze(problem, context)

        try:
            if result.strip().startswith('{'):
                return json.loads(result)
            return {"raw_response": result}
        except json.JSONDecodeError:
            return {"raw_response": result}

    def _build_analysis_prompt(
        self,
        problem: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建分析提示词"""
        return f"""你是一个专业的旅行规划优化师。请对以下旅行规划问题进行深度分析和优化。

问题描述：
{problem}

已收集的信息：
{json.dumps(context or {}, ensure_ascii=False, indent=2)}

你的任务：
1. **路线优化**：分析多段行程的最优顺序和连接方式
2. **时间安排**：每个目的地的合理停留时间
3. **预算分配**：根据各段行程的物价和景点密度分配预算
4. **风险评估**：识别天气、交通、时间等风险
5. **备选方案**：提供经济型、舒适型等不同方案

输出JSON格式（纯JSON，不要markdown代码块）：
{{
  "route_optimization": "路线优化建议",
  "time_arrangement": "时间安排建议",
  "budget_allocation": {{
    "城市名": 预算金额
  }},
  "risk_warnings": ["风险1", "风险2"],
  "alternative_plans": [
    {{
      "name": "方案名称",
      "description": "方案描述",
      "total_cost": 总费用,
      "pros": ["优点1"],
      "cons": ["缺点1"]
    }}
  ],
  "final_recommendation": "最终建议"
}}
"""


# 全局 R1 实例
_r1_instance: Optional[DeepSeekR1Analyzer] = None


def get_r1_instance() -> DeepSeekR1Analyzer:
    """获取全局 R1 实例"""
    global _r1_instance
    if _r1_instance is None:
        _r1_instance = DeepSeekR1Analyzer()
    return _r1_instance