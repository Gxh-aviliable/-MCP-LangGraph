"""测试数据模型验证

测试 Pydantic 数据模型的验证逻辑：
- TripPlan, TripRequest
- WeatherInfo 温度解析
- Attraction, Hotel, Meal 等
"""
import pytest
from pydantic import ValidationError
from backend.model.schemas import (
    TripPlan,
    TripRequest,
    ChatRequest,
    ChatResponse,
    WeatherInfo,
    Attraction,
    Hotel,
    Meal,
    Location,
    Budget,
    DayPlan,
)


class TestLocation:
    """测试位置模型"""

    def test_valid_location(self):
        """测试有效位置"""
        location = Location(longitude=116.4, latitude=39.9)
        assert location.longitude == 116.4
        assert location.latitude == 39.9

    def test_missing_fields(self):
        """测试缺少必要字段"""
        with pytest.raises(ValidationError):
            Location(longitude=116.4)  # 缺少 latitude


class TestAttraction:
    """测试景点模型"""

    def test_valid_attraction(self):
        """测试有效景点"""
        attraction = Attraction(
            name="故宫",
            address="北京市东城区",
            location=Location(longitude=116.4, latitude=39.9),
            visit_duration=120,
            description="皇家宫殿"
        )
        assert attraction.name == "故宫"
        assert attraction.visit_duration == 120

    def test_default_values(self):
        """测试默认值"""
        attraction = Attraction(
            name="故宫",
            address="北京市东城区",
            location=Location(longitude=116.4, latitude=39.9),
            visit_duration=120,
            description="皇家宫殿"
        )
        assert attraction.ticket_price == 0  # 默认值
        assert attraction.category == "景点"

    def test_rating_range(self):
        """测试评分范围"""
        # 有效评分
        attraction = Attraction(
            name="故宫",
            address="北京市东城区",
            location=Location(longitude=116.4, latitude=39.9),
            visit_duration=120,
            description="皇家宫殿",
            rating=4.5
        )
        assert attraction.rating == 4.5

        # 无效评分（超过5）
        with pytest.raises(ValidationError):
            Attraction(
                name="故宫",
                address="北京市东城区",
                location=Location(longitude=116.4, latitude=39.9),
                visit_duration=120,
                description="皇家宫殿",
                rating=6.0
            )

    def test_visit_duration_positive(self):
        """测试游览时间必须为正数"""
        with pytest.raises(ValidationError):
            Attraction(
                name="故宫",
                address="北京市东城区",
                location=Location(longitude=116.4, latitude=39.9),
                visit_duration=0,  # 必须大于0
                description="皇家宫殿"
            )


class TestWeatherInfo:
    """测试天气信息模型"""

    def test_valid_weather(self):
        """测试有效天气信息"""
        weather = WeatherInfo(
            date="2024-04-01",
            day_weather="晴",
            night_weather="晴",
            day_temp=16,
            night_temp=8,
            wind_direction="北",
            wind_power="3级"
        )
        assert weather.day_temp == 16

    def test_temperature_string_parsing(self):
        """测试温度字符串解析（"16°C" -> 16）"""
        weather = WeatherInfo(
            date="2024-04-01",
            day_weather="晴",
            night_weather="晴",
            day_temp="16°C",  # 字符串形式
            night_temp="8℃",
            wind_direction="北",
            wind_power="3级"
        )
        assert weather.day_temp == 16
        assert weather.night_temp == 8

    def test_temperature_with_degree_symbol(self):
        """测试带度数符号的温度"""
        weather = WeatherInfo(
            date="2024-04-01",
            day_weather="晴",
            night_weather="晴",
            day_temp="16°",
            night_temp="8°",
            wind_direction="北",
            wind_power="3级"
        )
        assert weather.day_temp == 16


class TestTripPlan:
    """测试旅行计划模型"""

    def test_valid_trip_plan(self):
        """测试有效的旅行计划"""
        plan = TripPlan(
            city="北京",
            start_date="2024-04-01",
            end_date="2024-04-03",
            days=[
                DayPlan(
                    date="2024-04-01",
                    day_index=0,
                    description="第一天",
                    transportation="地铁",
                    accommodation="酒店"
                )
            ],
            overall_suggestions="建议早起"
        )
        assert plan.city == "北京"
        assert plan.origin == ""  # 默认值

    def test_missing_required_fields(self):
        """测试缺少必要字段"""
        with pytest.raises(ValidationError):
            TripPlan(
                city="北京",
                # 缺少 start_date, end_date, days
            )

    def test_optional_fields(self):
        """测试可选字段"""
        plan = TripPlan(
            city="北京",
            start_date="2024-04-01",
            end_date="2024-04-03",
            days=[],
            overall_suggestions="建议"
        )
        assert plan.transport_options == []
        assert plan.weather_info == []
        assert plan.budget is None


class TestTripRequest:
    """测试旅行请求模型"""

    def test_valid_request(self):
        """测试有效的请求"""
        request = TripRequest(
            city="北京",
            start_date="2024-04-01",
            end_date="2024-04-03"
        )
        assert request.city == "北京"
        assert request.origin is None
        assert request.interests == []

    def test_optional_fields(self):
        """测试可选字段"""
        request = TripRequest(
            city="北京",
            start_date="2024-04-01",
            end_date="2024-04-03",
            origin="上海",
            interests=["历史", "美食"],
            budget_per_day=500,
            accommodation_type="中档"
        )
        assert request.origin == "上海"
        assert request.interests == ["历史", "美食"]
        assert request.budget_per_day == 500


class TestChatRequest:
    """测试对话请求模型"""

    def test_first_chat(self):
        """测试首次对话（无 session_id）"""
        request = ChatRequest(message="我想去北京")
        assert request.message == "我想去北京"
        assert request.session_id is None

    def test_continuation_chat(self):
        """测试后续对话（有 session_id）"""
        request = ChatRequest(
            session_id="test-session-123",
            message="4月1号出发"
        )
        assert request.session_id == "test-session-123"


class TestChatResponse:
    """测试对话响应模型"""

    def test_success_response(self):
        """测试成功响应"""
        response = ChatResponse(
            session_id="test-session",
            reply="好的，我来帮您规划",
            stage="collecting"
        )
        assert response.success == True
        assert response.missing_fields == []

    def test_error_response(self):
        """测试错误响应"""
        response = ChatResponse(
            success=False,
            session_id="test-session",
            reply="发生错误",
            stage="collecting"
        )
        assert response.success == False


class TestBudget:
    """测试预算模型"""

    def test_default_values(self):
        """测试默认值"""
        budget = Budget()
        assert budget.transport == 0
        assert budget.total == 0

    def test_calculated_total(self):
        """测试预算计算"""
        budget = Budget(
            transport=500,
            total_attractions=200,
            total_hotels=1000,
            total_meals=300,
            total=2000
        )
        assert budget.total == 2000


class TestDayPlan:
    """测试每日行程模型"""

    def test_valid_day_plan(self):
        """测试有效的每日行程"""
        day = DayPlan(
            date="2024-04-01",
            day_index=0,
            description="第一天行程",
            transportation="地铁",
            accommodation="酒店"
        )
        assert day.attractions == []
        assert day.meals == []

    def test_with_attractions_and_meals(self):
        """测试包含景点和餐饮的行程"""
        day = DayPlan(
            date="2024-04-01",
            day_index=0,
            description="第一天",
            transportation="地铁",
            accommodation="酒店",
            attractions=[
                Attraction(
                    name="故宫",
                    address="北京",
                    location=Location(longitude=116.4, latitude=39.9),
                    visit_duration=120,
                    description="宫殿"
                )
            ],
            meals=[
                Meal(type="breakfast", name="酒店早餐")
            ]
        )
        assert len(day.attractions) == 1
        assert len(day.meals) == 1