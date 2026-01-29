
if __name__ == "__main__":
    import re
    output_text="""基于搜索结果，我为您筛选出北京靠近故宫和国家博物馆的五星级酒店。以下是符合您要求的酒店列表（JSON格式）
：

```json
{
  "hotels": [
    {
      "name": "北京王府井文华东方酒店",
      "address": "王府井大街269号5F(王府井地铁站E3东北口步行370米)",
      "coordinates": "116.410063,39.912598",
      "rating": "4.8",
      "star_level": "五星级",
      "business_area": "东单",
      "type": "住宿服务;宾馆酒店;五星级宾馆|体育休闲服务;娱乐场所;酒吧",
      "proximity_to_attractions": "距离故宫约1.5公里，距离国家博物馆约2公里",
      "transportation": "靠近王府井地铁站，交通便利"
    },
    {
      "name": "北京饭店诺金-王府井",
      "address": "东长安街33号B座(王府井地铁站C1西北口步行120米)",
      "coordinates": "116.409189,39.908793",clr
      "rating": "4.6",
      "star_level": "五星级",
      "business_area": "东单",
      "type": "住宿服务;宾馆酒店;五星级宾馆",
      "proximity_to_attractions": "距离故宫约1.8公里，距离国家博物馆约1.2公里",
      "transportation": "紧邻王府井地铁站，交通极其便利"
    },
    {
      "name": "北京饭店",
      "address": "东长安街33号",
      "coordinates": "116.409385,39.908798",
      "rating": "4.5",
      "star_level": "五星级",
      "business_area": "东单",
      "type": "住宿服务;宾馆酒店;五星级宾馆|餐饮服务;餐饮相关场所;餐饮相关",
      "proximity_to_attractions": "距离故宫约1.8公里，距离国家博物馆约1.2公里",
      "transportation": "位于东长安街，交通便利"
    },
    {
      "name": "北京华尔道夫酒店",
      "address": "金鱼胡同5-15号(金鱼胡同地铁站B东口步行210米)",
      "coordinates": "116.413998,39.915951",
      "rating": "4.8",
      "star_level": "五星级",
      "business_area": "灯市口",
      "type": "住宿服务;宾馆酒店;五星级宾馆|餐饮服务;餐饮相关场所;餐饮相关",
      "proximity_to_attractions": "距离故宫约1.2公里，距离国家博物馆约2.5公里",
      "transportation": "靠近金鱼胡同地铁站，交通便利"
    },
    {
      "name": "北京东方君悦大酒店",
      "address": "东长安街1号",
      "coordinates": "116.414464,39.909821",
      "rating": "4.8",
      "star_level": "五星级",
      "business_area": "东单",
      "type": "住宿服务;宾馆酒店;五星级宾馆|餐饮服务;餐饮相关场所;餐饮相关",
      "proximity_to_attractions": "距离故宫约1.5公里，距离国家博物馆约1.5公里",
      "transportation": "位于东长安街核心位置，交通便利"
    },
    {
      "name": "北京前门文华东方酒店",
      "address": "草厂十条1号",
      "coordinates": "116.409670,39.896876",
      "rating": "4.8",
      "star_level": "五星级",
      "business_area": "珠市口",
      "type": "住宿服务;宾馆酒店;宾馆酒店",
      "proximity_to_attractions": "距离国家博物馆约1公里，距离故宫约2.5公里",
      "transportation": "靠近前门地区，交通便利"
    }
  ],
  "summary": {
    "total_hotels": 6,
    "average_rating": "4.72",
    "location_advantage": "所有酒店均位于北京市中心，靠近故宫和国家博物馆等主要景点",
    "transportation_advantage": "多数酒店靠近地铁站（王府井站、金鱼胡同站等），交通便利",
    "recommendation": "这些五星级酒店都符合您的要求，其中北京饭店诺金-王府井和北京东方君悦大酒店位置最为优越，同时靠近故宫和国家博物馆"
  }
}
```

**选择建议：**
1. **最佳地理位置**：北京饭店诺金-王府井和北京东方君悦大酒店位置最优，同时靠近故宫和国家博物馆
2. **最高评分**：北京王府井文华东方酒店、北京华尔道夫酒店、北京东方君悦大酒店和北京前门文华东方酒店评分均为4.8分
3. **交通最便利**：北京饭店诺金-王府井距离王府井地铁站仅120米，交通最为便利

所有酒店都提供五星级服务，您可以根据具体预算和偏好进行选择。"""
    import json
    json_pattern = r'(\[[\s\S]*?\]|\{[\s\S]*?\})'
    matches = re.findall(json_pattern, output_text)
    i=0
    for match in matches:
        try:
            i+=1
            print("当前是第"+str(i)+"个JSON:")
            print("Extracted JSON:")
            print(json.loads(match))
        except Exception as e:
            print(f"Error parsing JSON: {e}")

