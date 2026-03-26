# 旅游规划 Agent 项目框架与执行逻辑



uvicorn backend.main:app --host 0.0.0.0 --port 8000

## 项目结构

```
intern_project/
├── .env                    # 环境变量配置（API Keys）
├── .env.example            # 环境变量示例
├── backend/
│   ├── __init__.py         # 后端模块入口
│   ├── agent/              # Agent 核心模块
│   │   ├── __init__.py     # Agent 模块入口
│   │   ├── trip_agent.py   # 主 Agent 类（TripChatSession, TripChatSystem）
│   │   ├── state.py        # 状态定义（ChatAgentState）
│   │   └── nodes/          # Agent 节点
│   │       ├── __init__.py
│   │       └── nodes.py    # 各专家节点实现
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py     # 配置管理
│   ├── model/
│   │   ├── __init__.py
│   │   └── schemas.py      # 数据模型定义
│   ├── prompts/
│   │   └── __init__.py     # 所有 Prompt 定义
│   └── requirements.txt    # Python 依赖
├── problem.md              # 问题分析文档1
├── problem2.md             # 问题分析文档2（测试结果）
└── ARCHITECTURE.md         # 本文档
```

## 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| **prompts** | `prompts/__init__.py` | 所有 Agent 的系统提示词 |
| **state** | `agent/state.py` | LangGraph 状态定义和初始状态创建 |
| **nodes** | `agent/nodes/nodes.py` | 各专家节点实现（景点、天气、酒店、规划） |
| **trip_agent** | `agent/trip_agent.py` | 主系统类和会话管理 |
| **schemas** | `model/schemas.py` | Pydantic 数据模型 |
| **settings** | `config/settings.py` | 配置加载和管理 |

## 代码行数对比

重构前：
- `trip_agent.py`: **760 行**（包含所有内容）

重构后：
- `prompts/__init__.py`: ~120 行（Prompt 定义）
- `agent/state.py`: ~60 行（状态定义）
- `agent/nodes/nodes.py`: ~260 行（节点实现）
- `agent/trip_agent.py`: ~200 行（主系统）
- **总计**: ~640 行，但分散在 4 个文件中，职责清晰

---

## 核心组件说明

### 1. 配置层 (`config/settings.py`)

```python
# 从 .env 文件加载配置
class Settings:
    deepseek_api_key: str      # DeepSeek API 密钥
    amap_maps_api_key: str     # 高德地图 API 密钥
    debug: bool                # 调试模式
```

### 2. 数据模型层 (`model/schemas.py`)

```
TripRequest          # 用户请求
├── city             # 城市
├── start_date       # 开始日期
├── end_date         # 结束日期
├── interests[]      # 兴趣偏好
├── budget_per_day   # 每日预算
└── ...

TripPlan             # 行程规划结果
├── city
├── start_date
├── end_date
├── days[]           # 每日行程
│   ├── DayPlan
│   │   ├── date
│   │   ├── attractions[]  # 景点列表
│   │   ├── meals[]        # 餐饮安排
│   │   └── hotel          # 酒店
├── weather_info[]   # 天气信息
└── budget           # 预算统计
```

### 3. Agent 层 (`agent/trip_agent.py`)

```
TripChatSystem           # 核心系统
├── initialize()         # 初始化 MCP 工具
├── _create_agent_node() # 创建专家节点
├── _plan_trip_node()    # 生成行程
└── _create_chat_graph() # 构建执行图

TripChatSession          # 会话管理
├── start()              # 开始规划
├── feedback()           # 处理反馈
└── get_current_plan()   # 获取当前行程
```

---

## 执行流程图

```
用户输入
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│                    TripChatSession.start()                    │
│                                                              │
│  输入: TripRequest {                                          │
│    city: "北京",                                              │
│    start_date: "2026-03-26",                                 │
│    end_date: "2026-03-27",                                   │
│    interests: ["历史古迹"]                                    │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│                    LangGraph 执行图                           │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │ 景点专家     │───▶│ 天气专家     │───▶│ 酒店专家     │       │
│  │             │    │             │    │             │       │
│  │ maps_text_  │    │ maps_weather│    │ maps_text_  │       │
│  │ search      │    │             │    │ search      │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│         │                 │                 │                │
│         ▼                 ▼                 ▼                │
│   attractions_data   weather_data      hotels_data           │
│                                                              │
│                        │                                     │
│                        ▼                                     │
│              ┌─────────────────┐                            │
│              │   行程规划器     │                            │
│              │                 │                            │
│              │  LLM + Schema   │                            │
│              └─────────────────┘                            │
│                        │                                     │
│                        ▼                                     │
│                   final_plan                                 │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
TripPlan (JSON 结果)
```

---

## 具体例子：北京2日历史古迹游

### 第一步：用户输入

```python
request = TripRequest(
    city="北京",
    start_date="2026-03-26",
    end_date="2026-03-27",
    interests=["历史古迹"],
    accommodation_type="中档酒店",
    budget_per_day=500
)
```

### 第二步：景点专家执行

```python
# Agent 调用 MCP 工具
工具: maps_text_search
参数: {
    "keywords": "历史古迹",
    "city": "北京"
}

# 高德地图 API 返回
{
    "pois": [
        {"name": "故宫博物院", "address": "景山前街4号", ...},
        {"name": "颐和园", "address": "新建宫门路19号", ...},
        {"name": "天坛公园", "address": "天坛东里甲1号", ...},
        {"name": "八达岭长城", "address": "G6京藏高速58号出口", ...},
        ...
    ]
}

# 提取数据存入 state.attractions_data
```

### 第三步：天气专家执行

```python
# Agent 调用 MCP 工具
工具: maps_weather
参数: {
    "city": "北京"
}

# 高德天气 API 返回
{
    "forecasts": [
        {
            "date": "2026-03-26",
            "day_weather": "晴",
            "night_weather": "晴",
            "day_temp": "16",
            "night_temp": "6",
            "wind_direction": "北",
            "wind_power": "3级"
        },
        {
            "date": "2026-03-27",
            "day_weather": "多云",
            ...
        }
    ]
}

# 提取数据存入 state.weather_data
```

### 第四步：酒店专家执行

```python
# Agent 调用 MCP 工具
工具: maps_text_search
参数: {
    "keywords": "酒店",
    "city": "北京"
}

# 返回酒店列表
{
    "pois": [
        {"name": "北京宝格丽酒店", "address": "新源南路8号院", ...},
        {"name": "北京艺栈青年酒店", "address": "新源南路甲3号", ...},
        ...
    ]
}

# 提取数据存入 state.hotels_data
```

### 第五步：行程规划器执行

```python
# 收集所有数据，构建 Prompt
context = f"""
根据以下信息为用户生成详细的旅行计划：

📍 用户需求：
- 城市: 北京
- 日期: 2026-03-26 至 2026-03-27 (2天)
- 兴趣: 历史古迹
- 住宿: 中档酒店
- 预算: 500元/天

【景点信息】
1. 故宫博物院 - 明清皇宫...
2. 颐和园 - 皇家园林...
3. 天坛公园 - 明清祭天场所...

【天气预报】
2026-03-26: 晴, 16℃
2026-03-27: 多云, 18℃

【酒店选项】
1. 北京宝格丽酒店
2. 北京艺栈青年酒店

请生成完整的 2 天行程计划。
"""

# LLM 生成结构化输出
chain = prompt | llm.with_structured_output(TripPlan, method="json_mode")
result = chain.invoke({"context": context})
```

### 第六步：输出结果

```json
{
  "city": "北京",
  "start_date": "2026-03-26",
  "end_date": "2026-03-27",
  "days": [
    {
      "date": "2026-03-26",
      "day_index": 0,
      "description": "故宫与天坛一日游",
      "transportation": "地铁",
      "accommodation": "北京艺栈青年酒店",
      "attractions": [
        {
          "name": "故宫博物院",
          "address": "景山前街4号",
          "visit_duration": 180,
          "description": "明清两代皇宫",
          "ticket_price": 60
        },
        {
          "name": "天坛公园",
          "address": "天坛东里甲1号",
          "visit_duration": 120,
          "description": "明清祭天场所",
          "ticket_price": 15
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "酒店早餐", "estimated_cost": 30},
        {"type": "lunch", "name": "故宫附近餐厅", "estimated_cost": 80},
        {"type": "dinner", "name": "王府井小吃街", "estimated_cost": 100}
      ]
    },
    {
      "date": "2026-03-27",
      "day_index": 1,
      "description": "颐和园游览",
      ...
    }
  ],
  "weather_info": [
    {
      "date": "2026-03-26",
      "day_weather": "晴",
      "day_temp": 16,
      ...
    }
  ],
  "overall_suggestions": "建议穿舒适鞋子，带好防晒用品...",
  "budget": {
    "total_attractions": 75,
    "total_hotels": 400,
    "total_meals": 420,
    "total": 895
  }
}
```

---

## 多轮对话流程

```
第一轮规划完成
       │
       ▼
┌──────────────────────────────────┐
│  用户反馈: "第一天景点有点多"      │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  意图解析器                       │
│  输出: {                          │
│    "intent": "modify_attractions",│
│    "target_days": [0],            │
│    "action": "remove",            │
│    "details": "减少景点数量"       │
│  }                                │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  行程调整器                       │
│  - 保持其他天数不变                │
│  - 只调整第0天景点                 │
│  - 输出新的 TripPlan              │
└──────────────────────────────────┘
       │
       ▼
更新后的行程 → 用户确认/继续反馈
```

---

## 关键代码路径

```
运行入口
    │
    ▼
interactive_main()                    # trip_agent.py:675
    │
    ├── TripChatSession()             # 创建会话
    │
    ├── session.start(request)        # 开始规划
    │       │
    │       ├── system.initialize()   # 初始化 MCP
    │       │       │
    │       │       └── MultiServerMCPClient  # 加载高德工具
    │       │
    │       └── graph.ainvoke()       # 执行 LangGraph
    │               │
    │               ├── attraction_expert  # 景点专家节点
    │               ├── weather_expert     # 天气专家节点
    │               ├── hotel_expert       # 酒店专家节点
    │               └── plan_trip          # 规划节点
    │
    └── session.feedback(user_input)  # 处理反馈
            │
            ├── _parse_intent_node()  # 解析意图
            └── _adjust_plan_node()   # 调整行程
```

---

## 数据流转图

```
┌─────────────┐
│ 用户输入     │
│ TripRequest │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 景点专家     │     │ 天气专家     │     │ 酒店专家     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│attractions  │     │ weather_data│     │ hotels_data │
│   _data     │     │             │     │             │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ 行程规划器   │
                    │             │
                    │ LLM + JSON  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ final_plan  │
                    │  TripPlan   │
                    └─────────────┘
```

---

## 运行命令

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 配置环境变量
cp ../.env.example ../.env
# 编辑 .env 填入 API Keys

# 3. 运行
python agent/trip_agent.py
```