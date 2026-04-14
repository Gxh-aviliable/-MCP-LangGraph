"""相对日期解析器

支持解析各种相对日期表达式：
- "明天"、"后天"、"大后天"
- "下周"、"下下周"
- "下个月"、"下下个月"
- "五一假期"、"十一假期"、"春节"
- "玩三天"、"一周"
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import re


class DateParser:
    """相对日期解析器

    将自然语言日期表达式转换为具体日期

    使用方式:
        parser = DateParser()
        date = parser.parse("下周去北京")
        # date = datetime(2026, 4, 13)  # 下周一
    """

    # 中国法定节假日
    HOLIDAYS = {
        "元旦": (1, 1),
        "春节": (1, 1),  # 农历，需要特殊处理
        "五一": (5, 1),
        "劳动节": (5, 1),
        "端午": (6, 1),  # 农历
        "中秋": (9, 1),  # 农历
        "十一": (10, 1),
        "国庆": (10, 1),
        "国庆节": (10, 1),
    }

    def __init__(self, reference_date: Optional[datetime] = None):
        """初始化日期解析器

        Args:
            reference_date: 参考日期（用于测试），默认为当前日期
        """
        self.reference_date = reference_date or datetime.now()

    def parse(self, text: str) -> Optional[datetime]:
        """解析文本中的相对日期表达式

        Args:
            text: 包含日期表达式的文本

        Returns:
            解析出的日期，如果无法解析则返回 None
        """
        text = text.lower().strip()

        # 尝试各种解析规则
        parsers = [
            self._parse_relative_days,
            self._parse_weeks,
            self._parse_months,
            self._parse_holidays,
            self._parse_specific_date,
        ]

        for parser in parsers:
            result = parser(text)
            if result:
                return result

        return None

    def parse_with_duration(self, text: str) -> Tuple[Optional[datetime], Optional[int]]:
        """解析文本中的日期和持续时间

        Args:
            text: 包含日期和持续时间的文本，如 "下周去玩三天"

        Returns:
            (开始日期, 持续天数)
        """
        start_date = self.parse(text)
        duration = self._extract_duration(text)

        return start_date, duration

    def _parse_relative_days(self, text: str) -> Optional[datetime]:
        """解析相对天数表达式

        支持的表达式：
        - 今天
        - 明天
        - 后天
        - 大后天
        """
        # Order matters: check longer keywords first to avoid substring matching
        # e.g., "大后天" contains "后天", so check "大后天" first
        relative_days = [
            ("今天", 0),
            ("今日", 0),
            ("明天", 1),
            ("明日", 1),
            ("大后天", 3),  # Must check before "后天"
            ("后天", 2),
        ]

        for keyword, days in relative_days:
            if keyword in text:
                return self.reference_date + timedelta(days=days)

        return None

    def _parse_weeks(self, text: str) -> Optional[datetime]:
        """解析周相关的日期表达式

        支持的表达式：
        - 下周（下周一）
        - 下下周
        - 这周末
        - 下周末
        """
        today = self.reference_date
        weekday = today.weekday()  # 0=周一, 6=周日

        # Order matters: check longer keywords first to avoid substring matching
        if "下下周" in text:
            # 下下周的周一
            days_until_next_monday = (7 - weekday) + 7
            return today + timedelta(days=days_until_next_monday + 7)

        # Check "下周末" before "下周" to avoid substring matching
        if "下周末" in text:
            # 下周六
            days_until_saturday = (5 - weekday)
            if days_until_saturday <= 0:
                days_until_saturday += 7
            return today + timedelta(days=days_until_saturday + 7)

        if "下周" in text:
            # 下周一
            days_until_next_monday = (7 - weekday) if weekday > 0 else 7
            return today + timedelta(days=days_until_next_monday)

        if "这周末" in text or "本周末" in text:
            # 这周六
            days_until_saturday = (5 - weekday)
            if days_until_saturday < 0:
                days_until_saturday += 7
            return today + timedelta(days=days_until_saturday)

        # "周X" 格式
        week_days = {
            "周一": 0, "星期一": 0,
            "周二": 1, "星期二": 1,
            "周三": 2, "星期三": 2,
            "周四": 3, "星期四": 3,
            "周五": 4, "星期五": 4,
            "周六": 5, "星期六": 5,
            "周日": 6, "星期日": 6, "星期天": 6,
        }

        for keyword, target_weekday in week_days.items():
            if keyword in text:
                days_ahead = target_weekday - weekday
                if days_ahead <= 0:  # 目标日期已过或就是今天
                    days_ahead += 7
                return today + timedelta(days=days_ahead)

        return None

    def _parse_months(self, text: str) -> Optional[datetime]:
        """解析月份相关的日期表达式

        支持的表达式：
        - 下个月
        - 下下个月
        - 月初
        - 月中
        - 月底
        """
        today = self.reference_date

        if "下下个月" in text:
            # 下下个月1号
            month = today.month + 2
            year = today.year
            if month > 12:
                month -= 12
                year += 1
            return datetime(year, month, 1)

        if "下个月" in text:
            # 下个月1号
            month = today.month + 1
            year = today.year
            if month > 12:
                month = 1
                year += 1
            return datetime(year, month, 1)

        return None

    def _parse_holidays(self, text: str) -> Optional[datetime]:
        """解析节假日日期

        支持的表达式：
        - 五一
        - 十一
        - 国庆
        - 元旦
        """
        today = self.reference_date
        year = today.year

        # 五一劳动节
        if "五一" in text or "劳动节" in text:
            may_day = datetime(year, 5, 1)
            # 如果已过，使用下一年
            if may_day < today:
                may_day = datetime(year + 1, 5, 1)
            return may_day

        # 十一国庆节
        if "十一" in text or "国庆" in text:
            national_day = datetime(year, 10, 1)
            if national_day < today:
                national_day = datetime(year + 1, 10, 1)
            return national_day

        # 元旦
        if "元旦" in text:
            new_year = datetime(year + 1, 1, 1)
            return new_year

        # 寒假（一般1月中旬到2月底）
        if "寒假" in text:
            # 简单处理：返回1月15日
            winter_break = datetime(year if today.month < 6 else year + 1, 1, 15)
            return winter_break

        # 暑假（一般7月到8月）
        if "暑假" in text:
            summer_break = datetime(year if today.month < 9 else year + 1, 7, 1)
            return summer_break

        return None

    def _parse_specific_date(self, text: str) -> Optional[datetime]:
        """解析具体日期格式

        支持的格式：
        - 7月1号
        - 7月1日
        - 2024年7月1日
        - 2024-07-01
        """
        today = self.reference_date
        year = today.year

        # 匹配 "X月X日/号" 格式
        pattern1 = r'(\d{1,2})月(\d{1,2})[日号]'
        match = re.search(pattern1, text)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            try:
                date = datetime(year, month, day)
                # 如果日期已过，使用下一年
                if date < today:
                    date = datetime(year + 1, month, day)
                return date
            except ValueError:
                pass

        # 匹配 "YYYY年X月X日" 格式
        pattern2 = r'(\d{4})年(\d{1,2})月(\d{1,2})[日号]'
        match = re.search(pattern2, text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            try:
                return datetime(year, month, day)
            except ValueError:
                pass

        # 匹配 "YYYY-MM-DD" 格式
        pattern3 = r'(\d{4})-(\d{1,2})-(\d{1,2})'
        match = re.search(pattern3, text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            try:
                return datetime(year, month, day)
            except ValueError:
                pass

        return None

    def _extract_duration(self, text: str) -> Optional[int]:
        """从文本中提取持续天数

        支持的表达式：
        - 玩三天
        - 一周
        - 5天
        """
        # 匹配 "X天" 格式
        pattern1 = r'[玩待呆]?(\d+)\s*天'
        match = re.search(pattern1, text)
        if match:
            return int(match.group(1))

        # 匹配中文数字
        chinese_numbers = {
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        }

        pattern2 = r'[玩待呆]?([一二三四五六七八九十])\s*天'
        match = re.search(pattern2, text)
        if match:
            return chinese_numbers.get(match.group(1), None)

        # 匹配 "一周" / "一个星期"
        if "一周" in text or "一个星期" in text:
            return 7

        if "两周" in text or "两个星期" in text:
            return 14

        return None

    # ========== 辅助方法（供外部调用） ==========

    def get_next_monday(self) -> datetime:
        """获取下周一的日期"""
        today = self.reference_date
        weekday = today.weekday()
        days_until_monday = (7 - weekday) if weekday > 0 else 7
        return today + timedelta(days=days_until_monday)

    def get_next_month_first(self) -> datetime:
        """获取下个月1号的日期"""
        today = self.reference_date
        month = today.month + 1
        year = today.year
        if month > 12:
            month = 1
            year += 1
        return datetime(year, month, 1)

    def get_holiday_date(self, holiday_name: str) -> Optional[datetime]:
        """获取指定节假日的日期

        Args:
            holiday_name: 节假日名称，如 "五一"、"十一"

        Returns:
            节假日的日期
        """
        text = f"我想{holiday_name}去玩"
        return self._parse_holidays(text)

    def get_date_range(
        self,
        start_text: str,
        duration: Optional[int] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """获取日期范围

        Args:
            start_text: 开始日期的文本描述
            duration: 持续天数（可选，会尝试从文本中提取）

        Returns:
            (开始日期字符串, 结束日期字符串)，格式为 YYYY-MM-DD
        """
        start_date = self.parse(start_text)

        if not start_date:
            return None, None

        # 如果没有提供持续时间，尝试从文本提取
        if duration is None:
            duration = self._extract_duration(start_text)

        start_str = start_date.strftime('%Y-%m-%d')

        if duration:
            end_date = start_date + timedelta(days=duration - 1)
            end_str = end_date.strftime('%Y-%m-%d')
        else:
            end_str = None

        return start_str, end_str


def parse_relative_date(text: str, reference_date: Optional[datetime] = None) -> Optional[datetime]:
    """便捷函数：解析相对日期

    Args:
        text: 包含日期表达式的文本
        reference_date: 参考日期

    Returns:
        解析出的日期
    """
    parser = DateParser(reference_date)
    return parser.parse(text)


def get_date_range_from_text(
    text: str,
    reference_date: Optional[datetime] = None
) -> Tuple[Optional[str], Optional[str]]:
    """便捷函数：从文本中提取日期范围

    Args:
        text: 包含日期信息的文本
        reference_date: 参考日期

    Returns:
        (开始日期, 结束日期)
    """
    parser = DateParser(reference_date)
    return parser.get_date_range(text)