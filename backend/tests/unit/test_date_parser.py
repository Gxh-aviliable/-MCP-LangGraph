"""Test Date Parser

Test various date parsing functionality:
- Relative dates (tomorrow, next week, next month)
- Holidays (May Day, National Day)
- Specific date formats
- Duration extraction
"""
import pytest
from datetime import datetime, timedelta
from backend.utils.date_parser import DateParser, parse_relative_date, get_date_range_from_text


class TestDateParserRelativeDays:
    """Test relative days parsing"""

    def test_today(self):
        """Test 'today'"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("今天去玩")
        assert result == datetime(2024, 4, 1)

    def test_tomorrow(self):
        """Test 'tomorrow'"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("明天出发")
        assert result == datetime(2024, 4, 2)

    def test_day_after_tomorrow(self):
        """Test 'day after tomorrow'"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("后天去北京")
        assert result == datetime(2024, 4, 3)

    def test_three_days_later(self):
        """Test 'three days later'"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("大后天")
        assert result == datetime(2024, 4, 4)


class TestDateParserWeeks:
    """Test week-related date parsing"""

    def test_next_week(self):
        """Test 'next week' (next Monday)"""
        # 2024-04-01 is Monday
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("下周去")
        assert result == datetime(2024, 4, 8)  # Next Monday

    def test_next_week_from_middle(self):
        """Test calculating next week from mid-week"""
        # 2024-04-03 is Wednesday
        parser = DateParser(reference_date=datetime(2024, 4, 3))
        result = parser.parse("下周")
        assert result == datetime(2024, 4, 8)  # Next Monday

    def test_this_weekend(self):
        """Test 'this weekend'"""
        # 2024-04-01 is Monday
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("这周末去玩")
        assert result.weekday() == 5  # Saturday
        assert result == datetime(2024, 4, 6)

    def test_next_weekend(self):
        """Test 'next weekend'"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("下周末")
        assert result.weekday() == 5  # Saturday
        assert result > datetime(2024, 4, 6)

    def test_specific_weekday(self):
        """Test specific weekday"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))  # Monday
        result = parser.parse("周三去")
        assert result.weekday() == 2  # Wednesday


class TestDateParserMonths:
    """Test month-related date parsing"""

    def test_next_month(self):
        """Test 'next month'"""
        parser = DateParser(reference_date=datetime(2024, 4, 15))
        result = parser.parse("下个月")
        assert result == datetime(2024, 5, 1)

    def test_next_month_year_rollover(self):
        """Test year rollover"""
        parser = DateParser(reference_date=datetime(2024, 12, 15))
        result = parser.parse("下个月")
        assert result == datetime(2025, 1, 1)

    def test_two_months_later(self):
        """Test 'two months later'"""
        parser = DateParser(reference_date=datetime(2024, 4, 15))
        result = parser.parse("下下个月")
        assert result == datetime(2024, 6, 1)


class TestDateParserHolidays:
    """Test holiday parsing"""

    def test_may_day(self):
        """Test 'May Day'"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("五一去玩")
        assert result == datetime(2024, 5, 1)

    def test_may_day_next_year(self):
        """Test May Day returns next year if passed"""
        parser = DateParser(reference_date=datetime(2024, 6, 1))
        result = parser.parse("五一")
        assert result == datetime(2025, 5, 1)

    def test_national_day(self):
        """Test 'National Day'"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("国庆去")
        assert result == datetime(2024, 10, 1)

    def test_new_year(self):
        """Test 'New Year'"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("元旦")
        assert result == datetime(2025, 1, 1)

    def test_summer_vacation(self):
        """Test 'summer vacation'"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("暑假去")
        assert result.month == 7

    def test_winter_vacation(self):
        """Test 'winter vacation'"""
        parser = DateParser(reference_date=datetime(2024, 10, 1))
        result = parser.parse("寒假")
        assert result.month == 1


class TestDateParserSpecificFormats:
    """Test specific date format parsing"""

    def test_month_day_format(self):
        """Test 'X month X day' format"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("5月1号去")
        assert result == datetime(2024, 5, 1)

    def test_year_month_day_format(self):
        """Test 'YYYY year X month X day' format"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("2024年5月1日")
        assert result == datetime(2024, 5, 1)

    def test_iso_format(self):
        """Test ISO format"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("2024-05-01")
        assert result == datetime(2024, 5, 1)

    def test_date_passed_uses_next_year(self):
        """Test passed date uses next year"""
        parser = DateParser(reference_date=datetime(2024, 6, 1))
        result = parser.parse("3月1号")  # March has passed
        assert result == datetime(2025, 3, 1)


class TestDateParserDuration:
    """Test duration extraction"""

    def test_extract_days(self):
        """Test extracting days"""
        parser = DateParser()
        duration = parser._extract_duration("玩三天")
        assert duration == 3

    def test_extract_chinese_number(self):
        """Test Chinese number"""
        parser = DateParser()
        duration = parser._extract_duration("玩五天")
        assert duration == 5

    def test_extract_one_week(self):
        """Test 'one week'"""
        parser = DateParser()
        duration = parser._extract_duration("玩一周")
        assert duration == 7

    def test_extract_two_weeks(self):
        """Test 'two weeks'"""
        parser = DateParser()
        duration = parser._extract_duration("玩两个星期")
        assert duration == 14


class TestDateParserParseWithDuration:
    """Test parsing with duration"""

    def test_parse_with_duration(self):
        """Test parsing date and duration"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        start_date, duration = parser.parse_with_duration("下周去玩三天")
        assert start_date == datetime(2024, 4, 8)
        assert duration == 3

    def test_get_date_range(self):
        """Test getting date range"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        start_str, end_str = parser.get_date_range("下周玩三天")
        assert start_str == "2024-04-08"
        assert end_str == "2024-04-10"  # 3 days: 8, 9, 10


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_parse_relative_date_function(self):
        """Test parse_relative_date function"""
        result = parse_relative_date("明天", reference_date=datetime(2024, 4, 1))
        assert result == datetime(2024, 4, 2)

    def test_get_date_range_from_text_function(self):
        """Test get_date_range_from_text function"""
        start, end = get_date_range_from_text(
            "下周去玩三天",
            reference_date=datetime(2024, 4, 1)
        )
        assert start == "2024-04-08"
        assert end == "2024-04-10"


class TestEdgeCases:
    """Test edge cases"""

    def test_empty_string(self):
        """Test empty string"""
        parser = DateParser()
        result = parser.parse("")
        assert result is None

    def test_no_date_keyword(self):
        """Test no date keyword"""
        parser = DateParser()
        result = parser.parse("我去北京玩")
        assert result is None

    def test_case_insensitive(self):
        """Test case insensitive"""
        parser = DateParser(reference_date=datetime(2024, 4, 1))
        result = parser.parse("明天".lower())
        assert result == datetime(2024, 4, 2)

    def test_leap_year(self):
        """Test leap year"""
        parser = DateParser(reference_date=datetime(2024, 2, 28))
        result = parser.parse("明天")  # 2024 is leap year
        assert result == datetime(2024, 2, 29)