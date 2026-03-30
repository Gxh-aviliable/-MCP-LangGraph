# 数据模型模块
from .schemas import (
    # 请求模型
    TripRequest, FeedbackRequest, ChatRequest,
    # 响应模型
    TripPlan, TripPlanResponse, ChatResponse,
    # 数据结构模型
    Attraction, WeatherInfo, Hotel, Meal,
    DayPlan, Budget, Location, CollectedInfo,
)

__all__ = [
    # 请求模型
    'TripRequest', 'FeedbackRequest', 'ChatRequest',
    # 响应模型
    'TripPlan', 'TripPlanResponse', 'ChatResponse',
    # 数据结构模型
    'Attraction', 'WeatherInfo', 'Hotel', 'Meal',
    'DayPlan', 'Budget', 'Location', 'CollectedInfo',
]