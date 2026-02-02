# AI 旅行规划助手 - 完整实现指南

## 项目概述

这是一个基于 **多智能体架构** 的 AI 旅行规划系统，采用：
- **后端**: FastAPI + LangGraph + Multi-Agent
- **前端**: Vue3 + Element Plus
- **通信**: HTTP + WebSocket (实时进度)

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Vue3 前端应用                            │
│          (表单输入、实时进度、结果展示)                      │
└──────────────┬──────────────────────────────────────────────┘
               │ HTTP / WebSocket
┌──────────────▼──────────────────────────────────────────────┐
│                   FastAPI 后端服务                           │
│         (API 接口、WebSocket 长连接、业务逻辑)              │
└──────────────┬──────────────────────────────────────────────┘
               │ 异步调用
┌──────────────▼──────────────────────────────────────────────┐
│                   LangGraph 多智能体                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 景点专家 │→ │ 天气专家 │→ │ 酒店专家 │→ │ 规划专家 │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       └─────────────┴─────────────┴─────────────┘           │
│                                                              │
│  每个智能体通过 MCP (Model Context Protocol) 调用工具       │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│                  MCP 工具服务层                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │ 高德地图 API │      │ 天气查询 API │                    │
│  └──────────────┘      └──────────────┘                    │
└──────────────────────────────────────────────────────────────┘
```

## 环境配置

### 前置条件

- Python 3.10+
- Node.js 16+
- npm 或 yarn

### 后端部署

1. **安装依赖**
```bash
cd backend
pip install -r requirements.txt
```

2. **配置环境变量** (可选，默认已硬编码)
```bash
# 创建 .env 文件
DEEPSEEK_API_KEY=sk-xxx
AMAP_MAPS_API_KEY=xxx
```

3. **运行服务**
```bash
# 方式一：直接运行
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 方式二：通过 Python
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

服务将在 http://localhost:8000 启动

### 前端部署

1. **安装依赖**
```bash
cd frontend
npm install
# 或
yarn install
```

2. **开发服务**
```bash
npm run dev
# 将在 http://localhost:5173 启动
```

3. **生产构建**
```bash
npm run build
# 输出到 dist 文件夹
```

## API 接口文档

### 健康检查

**GET** `/health`

```json
{
  "status": "healthy",
  "timestamp": "2026-01-30T10:00:00",
  "service": "trip-planner"
}
```

### 获取热门城市

**GET** `/api/cities`

```json
{
  "success": true,
  "data": [
    {
      "name": "北京",
      "description": "中国首都，历史文化名城"
    }
  ]
}
```

### 获取兴趣分类

**GET** `/api/interests`

```json
{
  "success": true,
  "data": [
    {
      "category": "历史文化",
      "items": ["故宫", "长城", "兵马俑"]
    }
  ]
}
```

### 获取住宿类型

**GET** `/api/accommodation-types`

```json
{
  "success": true,
  "data": [
    {
      "name": "五星级",
      "description": "高端豪华酒店"
    }
  ]
}
```

### 生成旅行计划 (HTTP 同步)

**POST** `/api/plan`

请求体:
```json
{
  "city": "北京",
  "start_date": "2026-01-30",
  "end_date": "2026-02-02",
  "interests": ["故宫", "国家博物馆"],
  "accommodation_type": "五星级",
  "budget_per_day": 1500,
  "transportation_mode": "地铁+出租车"
}
```

响应:
```json
{
  "success": true,
  "message": "行程规划成功",
  "data": {
    "city": "北京",
    "start_date": "2026-01-30",
    "end_date": "2026-02-02",
    "days": [...],
    "weather_info": [...],
    "budget": {...},
    "overall_suggestions": "..."
  }
}
```

### WebSocket 实时规划

**WS** `/ws/plan`

客户端发送消息:
```json
{
  "action": "plan",
  "data": {
    "city": "北京",
    "start_date": "2026-01-30",
    "end_date": "2026-02-02",
    "interests": ["故宫"],
    "accommodation_type": "五星级",
    "budget_per_day": 1500,
    "transportation_mode": "地铁+出租车"
  }
}
```

服务器响应消息类型:

**start** - 开始规划
```json
{
  "type": "start",
  "message": "开始规划 北京 的旅行计划...",
  "timestamp": "2026-01-30T10:00:00"
}
```

**progress** - 进度更新
```json
{
  "type": "progress",
  "message": "### 景点专家汇报\n- 收集到 5 条数据\n",
  "timestamp": "2026-01-30T10:00:05"
}
```

**success** - 规划完成
```json
{
  "type": "success",
  "message": "行程规划完成",
  "data": {...},
  "timestamp": "2026-01-30T10:00:30"
}
```

**error** - 错误
```json
{
  "type": "error",
  "message": "规划过程出错: ...",
  "timestamp": "2026-01-30T10:00:30"
}
```

**warning** - 警告
```json
{
  "type": "warning",
  "message": "缺少天气信息",
  "timestamp": "2026-01-30T10:00:15"
}
```

## 项目结构

### 后端结构
```
backend/
├── api/
│   └── main.py                 # FastAPI 主应用
├── agent/
│   ├── demo_trip_agent.py      # 多智能体系统
│   └── demo.py                 # 示例脚本
├── model/
│   ├── schemas.py              # 数据模型定义
│   └── demo.py                 # 模型测试
├── tests/                       # 测试目录
├── requirements.txt             # Python 依赖
└── README.md                    # 后端文档
```

### 前端结构
```
frontend/
├── src/
│   ├── components/
│   │   ├── TripForm.vue        # 旅行表单
│   │   └── TripResult.vue      # 结果展示
│   ├── stores/
│   │   └── tripStore.js        # Pinia 状态管理
│   ├── utils/
│   │   └── api.js              # API 客户端
│   ├── App.vue                 # 根组件
│   └── main.js                 # 应用入口
├── index.html                   # HTML 模板
├── vite.config.js              # Vite 配置
├── package.json                # Node 依赖
└── README.md                    # 前端文档
```

## 核心功能说明

### 1. 多智能体工作流

系统由 4 个专家智能体组成，按顺序协同工作：

#### 景点专家 (Attraction Expert)
- **职责**: 搜索并收集真实景点信息
- **工具**: `maps_text_search` (高德地图)
- **输出**: 景点列表 (名称、地址、坐标、评分、门票)

#### 天气专家 (Weather Expert)
- **职责**: 查询旅行期间的天气预报
- **工具**: `maps_weather` (高德天气)
- **输出**: 每日天气 (温度、风向、风力)

#### 酒店专家 (Hotel Expert)
- **职责**: 推荐靠近景点的优质酒店
- **工具**: `maps_text_search` (高德地图)
- **输出**: 酒店列表 (名称、地址、价格、评分)

#### 规划专家 (Planner Expert)
- **职责**: 整合所有数据生成完整行程
- **工具**: LLM 结构化输出
- **输出**: 结构化旅行计划 (JSON)

### 2. 状态流转

```
输入请求
    ↓
景点专家 → attractions_data
    ↓
天气专家 → weather_data
    ↓
酒店专家 → hotels_data
    ↓
规划专家 → TripPlan (最终结果)
```

### 3. 数据模型

```python
TripPlan
├── city: str
├── start_date: str
├── end_date: str
├── days: List[DayPlan]
│   ├── date: str
│   ├── attractions: List[Attraction]
│   │   ├── name: str
│   │   ├── address: str
│   │   ├── location: Location
│   │   ├── visit_duration: int
│   │   └── ticket_price: int
│   ├── hotel: Hotel
│   │   ├── name: str
│   │   ├── location: Location
│   │   ├── price_range: str
│   │   └── estimated_cost: int
│   └── meals: List[Meal]
│       ├── type: str (breakfast/lunch/dinner/snack)
│       ├── name: str
│       └── estimated_cost: int
├── weather_info: List[WeatherInfo]
├── budget: Budget
└── overall_suggestions: str
```

## 使用示例

### Python 客户端

```python
import asyncio
import json
from backend.agent.demo_trip_agent import TripGraphSystem
from backend.model.schemas import TripRequest

async def main():
    # 初始化系统
    system = TripGraphSystem(
        api_key="sk-xxx",
        amap_key="xxx"
    )
    await system.initialize()
    
    # 创建图
    app = system.create_graph()
    
    # 准备请求
    request = TripRequest(
        city="北京",
        start_date="2026-01-30",
        end_date="2026-02-02",
        interests=["故宫", "国家博物馆"],
        accommodation_type="五星级",
        budget_per_day=1500,
        transportation_mode="地铁+出租车"
    )
    
    # 执行规划
    inputs = {
        "city": request.city,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "interests": request.interests,
        "accommodation_type": request.accommodation_type,
        "budget_per_day": request.budget_per_day,
        "transportation_mode": request.transportation_mode,
        "attractions_data": [],
        "weather_data": [],
        "hotels_data": [],
        "context": [],
        "execution_errors": [],
        "final_plan": None,
    }
    
    result = await app.ainvoke(inputs)
    
    # 输出结果
    if result["final_plan"]:
        print(json.dumps(result["final_plan"], indent=2, ensure_ascii=False))
    else:
        print("规划失败")

if __name__ == "__main__":
    asyncio.run(main())
```

### JavaScript 客户端

```javascript
// 使用 HTTP API
const response = await fetch('/api/plan', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    city: '北京',
    start_date: '2026-01-30',
    end_date: '2026-02-02',
    interests: ['故宫', '国家博物馆'],
    accommodation_type: '五星级',
    budget_per_day: 1500,
    transportation_mode: '地铁+出租车'
  })
})

const data = await response.json()
console.log(data)
```

```javascript
// 使用 WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/plan')

ws.onopen = () => {
  ws.send(JSON.stringify({
    action: 'plan',
    data: {
      city: '北京',
      start_date: '2026-01-30',
      end_date: '2026-02-02',
      interests: ['故宫'],
      accommodation_type: '五星级',
      budget_per_day: 1500,
      transportation_mode: '地铁+出租车'
    }
  }))
}

ws.onmessage = (event) => {
  const message = JSON.parse(event.data)
  console.log(`[${message.type}] ${message.message}`)
}
```

## 前端功能特点

### 交互界面
- ✨ 美观现代的渐变色设计
- 📱 完全响应式，支持移动端
- ⚡ 实时进度显示
- 🎯 实时表单验证

### 功能特性
- 📋 完整的旅行表单
- 📅 日期范围选择
- 🎨 多选兴趣爱好
- 💰 实时预算计算
- 🌍 热门城市推荐
- 📊 详细的行程展示
- 📈 预算分析图表
- 🌤️ 天气预报卡片
- 🏨 酒店信息展示
- 🍽️ 餐饮推荐
- 📥 JSON 导出
- 🖨️ 打印功能

## 故障排除

### 后端问题

1. **MCP 工具加载失败**
   - 检查 AMAP_MAPS_API_KEY 是否正确
   - 确保 amap-mcp-server 已安装
   - 运行: `pip install amap-mcp-server`

2. **LLM 连接失败**
   - 检查 DeepSeek API Key
   - 检查网络连接
   - 确保 base_url 正确

3. **异步执行错误**
   - 升级到最新版本的 langchain
   - 检查 Python 版本 >= 3.10

### 前端问题

1. **Vite 代理问题**
   - 确保后端服务运行在 8000 端口
   - 检查 vite.config.js 中的代理配置
   - 清除浏览器缓存

2. **WebSocket 连接失败**
   - 检查浏览器控制台错误
   - 确保后端支持 WebSocket
   - 尝试使用 HTTP 备选方案

3. **Element Plus 样式加载失败**
   - 清除 node_modules
   - 重新安装依赖: `npm install`
   - 清除浏览器缓存

## 部署建议

### 生产环境

1. **后端部署**
```bash
# 使用 Gunicorn + Uvicorn
pip install gunicorn
gunicorn api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 或使用 Docker
docker build -t trip-planner-api .
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=xxx -e AMAP_MAPS_API_KEY=xxx trip-planner-api
```

2. **前端部署**
```bash
# 构建静态文件
npm run build

# 使用 Nginx 提供
# 配置 Nginx 反向代理到后端

# 或部署到 CDN (Vercel, Netlify 等)
```

3. **反向代理配置** (Nginx)
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # 前端静态文件
    location / {
        root /var/www/trip-planner/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # WebSocket
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

## 性能优化

1. **缓存热门城市数据**
   - 在应用启动时预加载
   - 使用 Redis 缓存参考数据

2. **并行执行智能体**
   - 天气和酒店查询可并行
   - 使用 asyncio.gather()

3. **限流和速率限制**
   - 添加 slowapi
   - 限制单用户请求频率

4. **数据库存储**
   - 保存用户规划历史
   - 收集使用统计

## 相关资源

- 🔗 [FastAPI 文档](https://fastapi.tiangolo.com/)
- 🔗 [Vue3 文档](https://vuejs.org/)
- 🔗 [Element Plus 文档](https://element-plus.org/)
- 🔗 [LangChain 文档](https://python.langchain.com/)
- 🔗 [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- 🔗 [高德地图 API](https://lbs.amap.com/)

## 许可证

MIT

## 作者

AI 旅行规划助手开发团队

---

**最后更新**: 2026-01-30
**版本**: 1.0.0
