"""智能查询分流模块

根据用户查询的复杂度，决定使用哪个模型处理：
- simple: 简单查询，Qwen3 主导
- complex: 复杂查询（预算紧张、特殊需求），R1 主导
- multi_destination: 多目的地，R1 主导
"""
import json
import re
from typing import Dict, Any, Optional
from datetime import datetime


# 多目的地关键词
MULTI_DEST_KEYWORDS = [
    "再去", "然后去", "接着去", "顺便去",
    "再到", "然后到", "接着到",
    "之后再", "之后去", "之后到"
]

# 特殊需求关键词
SPECIAL_NEEDS_KEYWORDS = [
    "老人", "儿童", "小孩", "孩子", "亲子",
    "残疾", "孕妇", "婴儿", "宝宝"
]


async def analyze_query_complexity(
    user_query: str,
    llm,
    collected_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """分析查询复杂度，决定使用哪个模型

    Args:
        user_query: 用户查询文本
        llm: 语言模型实例
        collected_info: 已收集的信息

    Returns:
        {
            "scenario_type": "simple" | "complex" | "multi_destination",
            "needs_r1": bool,
            "extraction": {...},  # 提取的信息
            "reason": "原因说明"
        }
    """
    today = datetime.now().strftime("%Y-%m-%d")
    current_year = datetime.now().year

    # 构建提取 prompt
    extraction_prompt = f"""You are a travel planning assistant. Today's date is {today}.

Your task: Extract key information from the user query and determine if it needs deep analysis.

RULES:
- Output ONLY valid JSON. NO explanations, NO markdown code blocks.
- Date conversion: "今天"/"today" = {today}, "明天"/"tomorrow" = +1 day, etc.
- Use Chinese for city names.
- Set "needs_deep_analysis" to true if:
  * Complex multi-city routes (e.g., "A和B", "A再去B")
  * Budget optimization needed (tight budget with many requirements)
  * Multiple conflicting constraints (e.g., elderly + children, limited time + many places)
  * Special needs: 老人, 小孩, 儿童, 亲子, etc.

Output this exact JSON structure:
{{
  "destination": "extracted destination city or cities (comma separated if multiple)",
  "origin": "extracted origin city",
  "travel_days": 0,
  "budget": 0,
  "travel_date": "YYYY-MM-DD",
  "preferences": ["preference1"],
  "needs_deep_analysis": false,
  "has_special_needs": false
}}

User query: {user_query}
"""

    try:
        response = await llm.ainvoke(extraction_prompt)
        content = response.content.strip()

        # 移除可能的markdown代码块
        if content.startswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1]) if len(lines) > 2 else content
            if content.startswith('json'):
                content = content[4:]

        extraction = json.loads(content)
        print(f"[Router] 提取信息: {extraction}")

    except Exception as e:
        print(f"[Router] 提取失败: {e}")
        extraction = {
            "destination": "",
            "origin": "",
            "travel_days": 0,
            "budget": 0,
            "travel_date": "",
            "preferences": [],
            "needs_deep_analysis": False,
            "has_special_needs": False
        }

    # 检测多目的地场景
    multi_dest_info = detect_multi_destination(user_query, extraction)

    # 确定场景类型
    if multi_dest_info.get('is_multi_destination', False):
        scenario_type = 'multi_destination'
        needs_r1 = True
        reason = f"多目的地场景: {multi_dest_info.get('detection_method')}"
        print(f"[Router] 检测到多目的地: {reason}")

    elif extraction.get('needs_deep_analysis', False):
        scenario_type = 'complex'
        needs_r1 = True
        reason = "需要深度分析(预算/约束复杂)"
        print(f"[Router] 检测到复杂场景: {reason}")

    elif extraction.get('has_special_needs', False):
        scenario_type = 'complex'
        needs_r1 = True
        reason = "包含特殊需求(老人/儿童等)"
        print(f"[Router] 检测到特殊需求: {reason}")

    else:
        # 检查是否有特殊需求关键词
        if any(kw in user_query for kw in SPECIAL_NEEDS_KEYWORDS):
            scenario_type = 'complex'
            needs_r1 = True
            reason = "包含特殊需求关键词"
        else:
            scenario_type = 'simple'
            needs_r1 = False
            reason = "简单场景，Qwen3主导"

    return {
        "scenario_type": scenario_type,
        "needs_r1": needs_r1,
        "extraction": extraction,
        "multi_dest_info": multi_dest_info,
        "reason": reason
    }


def detect_multi_destination(user_query: str, extraction: dict) -> dict:
    """检测是否为多目的地场景

    Args:
        user_query: 用户查询
        extraction: 提取的信息

    Returns:
        {
            "is_multi_destination": bool,
            "detected_keywords": [],
            "raw_destination_text": str,
            "detection_method": str
        }
    """
    # 1. 排除往返场景
    roundtrip_keywords = ["往返", "来回", "回程", "返程", "返回"]
    if any(kw in user_query for kw in roundtrip_keywords):
        return {
            'is_multi_destination': False,
            'detected_keywords': [],
            'raw_destination_text': extraction.get('destination', ''),
            'detection_method': 'roundtrip_excluded'
        }

    # 2. 检测多目的地关键词
    detected_keywords = [kw for kw in MULTI_DEST_KEYWORDS if kw in user_query]
    if detected_keywords:
        return {
            'is_multi_destination': True,
            'detected_keywords': detected_keywords,
            'raw_destination_text': extraction.get('destination', ''),
            'detection_method': 'keyword'
        }

    # 3. 检测目的地字段中的多个城市
    destination = extraction.get('destination', '') or ''
    origin = extraction.get('origin', '') or ''

    # 统一分隔符
    norm = destination.replace(',', '，').replace('、', '，').replace('和', '，')
    cities = [c.strip() for c in norm.split('，') if c.strip()]

    # 去重保持顺序
    unique_cities = []
    for c in cities:
        if c not in unique_cities:
            unique_cities.append(c)

    if len(unique_cities) >= 3:
        return {
            'is_multi_destination': True,
            'detected_keywords': [],
            'raw_destination_text': destination,
            'detection_method': 'comma_separated_3plus'
        }

    if len(unique_cities) == 2:
        # 如果两个城市中包含出发地，通常是往返
        if origin and origin in unique_cities:
            return {
                'is_multi_destination': False,
                'detected_keywords': [],
                'raw_destination_text': destination,
                'detection_method': 'origin_pair_excluded'
            }
        # 两个且都不是出发地 -> 多目的地
        return {
            'is_multi_destination': True,
            'detected_keywords': [],
            'raw_destination_text': destination,
            'detection_method': 'comma_separated_2'
        }

    return {
        'is_multi_destination': False,
        'detected_keywords': [],
        'raw_destination_text': destination
    }


def get_scenario_description(scenario_type: str) -> str:
    """获取场景类型的中文描述"""
    descriptions = {
        'simple': '简单场景',
        'complex': '复杂场景',
        'multi_destination': '多目的地场景'
    }
    return descriptions.get(scenario_type, '未知场景')