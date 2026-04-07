"""数据模型定义"""
from pydantic import BaseModel,Field,field_validator
from typing import Optional,List


""""=======================响应模型========================"""
class Location(BaseModel):
    """地理位置"""
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")

class Attraction(BaseModel):  
    """景点信息"""  
    name: str = Field(...,description="景点名称")
    address: str = Field(...,description="地址")
    location: Location = Field(...,description="经纬度坐标")
    visit_duration: int = Field(...,description="建议游览时间(分钟)",gt=0)
    description: str = Field(...,description="景点描述")
    category: Optional[str] = Field(default="景点",description="景点类别")
    rating: Optional[float] = Field(default=None,ge=0,le=5,description="评分")
    image_url: Optional[str] = Field(default=None,description="图片URL")
    ticket_price: int = Field(default=0,ge=0,description="门票价格(元)")

class Meal(BaseModel):
    """餐饮信息"""
    type: str = Field(...,description="餐饮类型：breakfast/lunch/dinner/snack")
    name: str = Field(...,description="餐饮名称")
    address: Optional[str] = Field(default=None,description="地址")
    location: Optional[Location] = Field(default=None,description="经纬度坐标")
    description: Optional[str] = Field(default=None,description="描述")
    estimated_cost: int = Field(default=0,description="预估费用(元)")

class Hotel(BaseModel):
    """酒店信息"""
    name: str = Field(...,description="酒店名称")
    address: str = Field(default="",description="酒店地址")
    location: Optional[Location] = Field(default=None,description="酒店位置")
    price_range: str = Field(default="",description="价格范围")
    rating: Optional[float] = Field(default=None,ge=0,le=5,description="评分")
    distance: str = Field(default="",description="距离景点距离")
    type: str = Field(default="",description="酒店类型")
    estimated_cost: int = Field(default=0,description="预估费用(元/晚)")

class Budget(BaseModel):
    """预算信息"""
    transport: int = Field(default=0, description="交通费用")
    total_attractions: int = Field(default=0,description="景点门票总费用")
    total_hotels: int = Field(default=0,description="酒店总费用")
    total_meals: int = Field(default=0,description="餐饮总费用")
    total_transportation: int = Field(default=0,description="交通总费用")
    total: int = Field(default=0,description="总费用")

class DayPlan(BaseModel):
    """单日行程"""
    date: str = Field(...,description="日期")
    day_index: int = Field(...,description="第几天(从0开始)")
    description: str = Field(...,description="当日行程描述")
    transportation: str = Field(...,description="交通方式")
    accommodation: str = Field(...,description="住宿安排")
    hotel: Optional[Hotel] = Field(default=None,description="酒店信息")
    attractions: List[Attraction] = Field(default_factory=list,description="景点列表")
    meals: List[Meal] = Field(default_factory=list,description="餐饮安排")

class WeatherInfo(BaseModel):
    """天气信息"""
    date: str = Field(...,description="日期")
    day_weather: str = Field(...,description="白天天气")
    night_weather: str = Field(...,description="夜间天气")
    day_temp: int = Field(...,description="白天温度(摄氏度)")
    night_temp: int = Field(...,description="夜间温度(摄氏度)")
    wind_direction: str = Field(...,description="风向")
    wind_power: str = Field(...,description="风力")

    @field_validator('day_temp','night_temp',mode='before')
    def parse_temperature(cls,v):
        """解析温度字符串："16°C" -> 16"""
        if isinstance(v,str):
            v = v.replace('°C','').replace('℃','').replace('°','').strip()
            try:
                return int(v)
            except ValueError:
                return 0  # 容错处理
        return v


class TransportOption(BaseModel):
    """交通方案"""
    type: str = Field(..., description="交通类型: train/driving/flight")
    name: str = Field(..., description="方案名称")
    duration: str = Field(default="", description="耗时")
    cost: int = Field(default=0, description="费用(元)")
    details: dict = Field(default_factory=dict, description="详细信息")


class RecommendedTransport(BaseModel):
    """推荐的交通方案"""
    type: str = Field(..., description="交通类型")
    name: str = Field(..., description="推荐的具体车次/路线")
    reason: str = Field(default="", description="推荐理由")


class TripPlan(BaseModel):
    """旅行计划"""
    origin: str = Field(default="", description="出发地")
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    transport_options: List[TransportOption] = Field(default_factory=list, description="交通方案列表")
    recommended_transport: Optional[RecommendedTransport] = Field(default=None, description="推荐的交通方案")
    days: List[DayPlan] = Field(..., description="每日行程")
    weather_info: List[WeatherInfo] = Field(default=[], description="天气信息")
    overall_suggestions: str = Field(..., description="总体建议")
    budget: Optional[Budget] = Field(default=None, description="预算信息")


class TripPlanResponse(BaseModel):
    """旅行计划响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[TripPlan] = Field(default=None, description="旅行计划数据")

""""=======================请求模型========================"""
class TripRequest(BaseModel):
    """旅行计划请求"""
    origin: Optional[str] = Field(default=None, description="出发城市")
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    interests: List[str] = Field(default_factory=list, description="兴趣偏好")
    budget_per_day: Optional[int] = Field(default=None, description="每日预算(元)")
    accommodation_type: Optional[str] = Field(default=None, description="住宿类型")
    transportation_mode: Optional[str] = Field(default=None, description="交通方式")


class FeedbackRequest(BaseModel):
    """反馈请求 - 用于多轮对话"""
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="用户反馈消息")


""""=======================对话模型========================"""
class ChatRequest(BaseModel):
    """对话请求 - 用于聊天式交互"""
    session_id: Optional[str] = Field(default=None, description="会话ID，首次可为空")
    message: str = Field(..., description="用户消息")


class CollectedInfo(BaseModel):
    """已收集的旅行信息"""
    origin: Optional[str] = Field(default=None, description="出发城市")
    city: Optional[str] = Field(default=None, description="目的地城市")
    start_date: Optional[str] = Field(default=None, description="开始日期")
    end_date: Optional[str] = Field(default=None, description="结束日期")
    interests: List[str] = Field(default_factory=list, description="兴趣偏好")
    budget_per_day: Optional[int] = Field(default=None, description="每日预算")
    accommodation_type: Optional[str] = Field(default=None, description="住宿类型")


class ChatResponse(BaseModel):
    """对话响应"""
    success: bool = Field(default=True, description="是否成功")
    session_id: str = Field(..., description="会话ID")
    reply: str = Field(..., description="机器人回复")
    stage: str = Field(..., description="对话阶段: greeting/collecting/confirming/planning/refining/done")
    collected_info: Optional[CollectedInfo] = Field(default=None, description="已收集信息")
    missing_fields: List[str] = Field(default_factory=list, description="缺失字段")
    plan: Optional[dict] = Field(default=None, description="行程计划(生成后返回)")