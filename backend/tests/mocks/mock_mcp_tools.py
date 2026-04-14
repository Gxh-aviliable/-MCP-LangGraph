"""Mock MCP 工具实现

提供高德地图和 12306 MCP 工具的 mock 实现，用于测试
"""
from typing import List, Dict, Any, Optional
from langchain_core.tools import Tool
import json


def create_mock_attraction_result(city: str = "北京") -> str:
    """生成模拟的景点搜索结果"""
    attractions = {
        "北京": [
            {"name": "故宫", "address": "北京市东城区景山前街4号", "location": {"longitude": 116.397128, "latitude": 39.917844}, "description": "中国明清两代的皇家宫殿", "rating": 4.8, "ticket_price": 60},
            {"name": "天安门", "address": "北京市东城区天安门广场", "location": {"longitude": 116.397455, "latitude": 39.909187}, "description": "中华人民共和国的象征", "rating": 4.7, "ticket_price": 0},
            {"name": "颐和园", "address": "北京市海淀区新建宫门路19号", "location": {"longitude": 116.275, "latitude": 39.9999}, "description": "中国清朝时期皇家园林", "rating": 4.6, "ticket_price": 30},
            {"name": "长城", "address": "北京市延庆区八达岭镇", "location": {"longitude": 116.5702, "latitude": 40.3539}, "description": "世界文化遗产", "rating": 4.9, "ticket_price": 40},
        ],
        "上海": [
            {"name": "外滩", "address": "上海市黄浦区中山东一路", "location": {"longitude": 121.490317, "latitude": 31.245417}, "description": "上海的标志性景观", "rating": 4.7, "ticket_price": 0},
            {"name": "东方明珠", "address": "上海市浦东新区世纪大道1号", "location": {"longitude": 121.499444, "latitude": 31.239583}, "description": "上海地标建筑", "rating": 4.5, "ticket_price": 199},
        ],
    }
    return json.dumps(attractions.get(city, attractions["北京"]), ensure_ascii=False)


def create_mock_weather_result(city: str = "北京") -> str:
    """生成模拟的天气查询结果"""
    weather = [
        {"date": "2024-04-01", "day_weather": "晴", "night_weather": "晴", "day_temp": 16, "night_temp": 8, "wind_direction": "北", "wind_power": "3级"},
        {"date": "2024-04-02", "day_weather": "多云", "night_weather": "晴", "day_temp": 18, "night_temp": 10, "wind_direction": "南", "wind_power": "2级"},
        {"date": "2024-04-03", "day_weather": "晴", "night_weather": "晴", "day_temp": 20, "night_temp": 12, "wind_direction": "东", "wind_power": "2级"},
    ]
    return json.dumps(weather, ensure_ascii=False)


def create_mock_hotel_result(location: str = "") -> str:
    """生成模拟的酒店搜索结果"""
    hotels = [
        {"name": "北京饭店", "address": "北京市东城区东长安街33号", "location": {"longitude": 116.407526, "latitude": 39.904088}, "rating": 4.5, "price_range": "800-1200元", "type": "豪华型"},
        {"name": "如家快捷酒店", "address": "北京市东城区王府井大街", "location": {"longitude": 116.410, "latitude": 39.915}, "rating": 4.0, "price_range": "200-300元", "type": "经济型"},
        {"name": "希尔顿酒店", "address": "北京市朝阳区东三环北路", "location": {"longitude": 116.46, "latitude": 39.95}, "rating": 4.6, "price_range": "1000-1500元", "type": "豪华型"},
    ]
    return json.dumps(hotels, ensure_ascii=False)


def create_mock_transport_result(origin: str = "北京", destination: str = "上海") -> str:
    """生成模拟的交通查询结果"""
    stations = {
        "北京": [{"station_code": "BJP", "station_name": "北京站"}, {"station_code": "VNP", "station_name": "北京南站"}],
        "上海": [{"station_code": "SHH", "station_name": "上海站"}, {"station_code": "AOH", "station_name": "上海虹桥站"}],
    }

    if "station" in origin.lower() or "station" in str(origin).lower():
        # 返回站点代码
        city = origin.replace("get-stations-code-in-city", "").strip() if isinstance(origin, str) else "北京"
        return json.dumps({"return": stations.get(city, stations["北京"])}, ensure_ascii=False)

    # 返回火车票
    tickets = [
        {"train_code": "G1", "from_station": "北京南", "to_station": "上海虹桥", "departure_time": "07:00", "arrival_time": "11:30", "run_time": "4小时30分", "price": 553},
        {"train_code": "G3", "from_station": "北京南", "to_station": "上海虹桥", "departure_time": "08:00", "arrival_time": "12:30", "run_time": "4小时30分", "price": 553},
        {"train_code": "G7", "from_station": "北京南", "to_station": "上海虹桥", "departure_time": "09:00", "arrival_time": "13:30", "run_time": "4小时30分", "price": 553},
    ]
    return json.dumps(tickets, ensure_ascii=False)


def create_mock_tools() -> List[Tool]:
    """创建模拟的 MCP 工具集

    Returns:
        工具列表，包含：
        - maps_text_search: 景点/地点搜索
        - maps_weather: 天气查询
        - maps_around_search: 周边搜索（酒店）
        - get-stations-code-in-city: 获取城市站点代码
        - get-tickets: 查询火车票
    """

    def mock_text_search(query: str) -> str:
        """模拟文本搜索"""
        if "景点" in query or "公园" in query or "博物馆" in query:
            city = "北京"
            for c in ["上海", "广州", "深圳", "杭州"]:
                if c in query:
                    city = c
                    break
            return create_mock_attraction_result(city)
        elif "酒店" in query:
            return create_mock_hotel_result()
        return "[]"

    def mock_weather(query: str) -> str:
        """模拟天气查询"""
        return create_mock_weather_result()

    def mock_around_search(query: str) -> str:
        """模拟周边搜索（酒店）"""
        return create_mock_hotel_result()

    def mock_get_stations(query: str) -> str:
        """模拟获取站点代码"""
        return create_mock_transport_result(query)

    def mock_get_tickets(query: str) -> str:
        """模拟查询火车票"""
        return create_mock_transport_result()

    tools = [
        Tool(
            name="maps_text_search",
            description="搜索地点、景点、酒店等",
            func=mock_text_search
        ),
        Tool(
            name="maps_weather",
            description="查询城市天气预报",
            func=mock_weather
        ),
        Tool(
            name="maps_around_search",
            description="周边搜索（酒店、餐厅等）",
            func=mock_around_search
        ),
        Tool(
            name="get-stations-code-in-city",
            description="获取城市的火车站站点代码",
            func=mock_get_stations
        ),
        Tool(
            name="get-tickets",
            description="查询火车票信息",
            func=mock_get_tickets
        ),
    ]

    return tools


# 预定义的工具列表（用于 fixtures）
MOCK_TOOLS = create_mock_tools()


def get_tool_by_name(name: str) -> Optional[Tool]:
    """根据名称获取工具"""
    for tool in MOCK_TOOLS:
        if tool.name == name:
            return tool
    return None