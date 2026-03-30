# 旅游规划 Agent 项目框架文档

> 文档更新日期: 2026-03-30
> 项目版本: 1.0.0

---

## 一、项目概述

### 1.1 项目简介

基于 LangGraph 多 Agent 架构的智能旅行规划系统，支持多轮对话交互，用户可通过自然语言反馈动态调整行程。

### 1.2 技术栈

| 层级 | 技术选型 |
|------|----------|
| **后端框架** | FastAPI |
| **LLM 框架** | LangGraph + LangChain |
| **LLM 模型** | DeepSeek Chat |
| **工具集成** | MCP (Model Context Protocol) + 高德地图 API |
| **前端框架** | Vue 3 + TypeScript |
| **构建工具** | Vite |
| **HTTP 客户端** | Axios |

### 1.3 核心功能

- ✅ 多专家协作：景点专家、天气专家、酒店专家串行执行
- ✅ 结构化输出：Pydantic 模型约束 LLM 输出格式
- ✅ 多轮对话：支持用户反馈动态调整行程
- ✅ 会话管理：过期清理机制，防止内存泄漏
- ✅ CORS 安全：配置化域名白名单

---

## 二、项目结构

```
intern_project/
├── .env                        # 环境变量配置（API Keys）
├── .env.example                # 环境变量示例
├── .gitignore                  # Git 忽略配置
├── .venv/                      # Python 虚拟环境
│
├── backend/                    # 后端代码
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── requirements.txt        # Python 依赖
│   │
│   ├── agent/                  # Agent 核心模块
│   │   ├── __init__.py         # 模块导出
│   │   ├── trip_agent.py       # 主 Agent 类（TripChatSession, TripChatSystem）
│   │   ├── state.py            # LangGraph 状态定义（ChatAgentState）
│   │   └── nodes/              # Agent 节点实现
│   │       ├── __init__.py     # 节点导出
│   │       └── nodes.py        # 各专家节点实现
│   │
│   ├── config/                 # 配置模块
│   │   ├── __init__.py
│   │   └── settings.py         # Pydantic Settings 配置
│   │
│   ├── model/                  # 数据模型
│   │   ├── __init__.py         # 模型导出
│   │   └── schemas.py          # Pydantic 数据模型定义
│   │
│   └── prompts/                # Prompt 模板
│       └── __init__.py         # 所有 Agent 的系统提示词
│
├── frontend/                   # 前端代码
│   ├── package.json            # NPM 配置
│   ├── vite.config.ts          # Vite 配置
│   ├── tsconfig.json           # TypeScript 配置
│   │
│   └── src/
│       ├── main.ts             # 应用入口
│       ├── App.vue             # 根组件
│       ├── api/
│       │   └── index.ts        # API 调用封装
│       └── components/
│           ├── HelloWorld.vue  # 示例组件
│           └── TripPlanner.vue # 主业务组件
│
├── test/                       # 测试代码
│   └── test_agent.py           # Agent 测试脚本
│
├── ARCHITECTURE.md             # 架构文档
├── QUICKSTART.md               # 快速启动指南
├── problem3.md                 # 代码审查报告
└── PROJECT_FRAMEWORK.md        # 本文档
```

---

## 三、模块详解

### 3.1 后端模块

#### 3.1.1 入口层 (`backend/main.py`)

**职责**: FastAPI 应用配置、路由定义、中间件配置

```
FastAPI App
├── CORS Middleware（安全配置）
├── SessionManager（会话管理器）
│   ├── 过期清理机制（默认1小时）
│   └── 后台异步清理任务
│
└── API Routes
    ├── GET  /                    # 健康检查
    ├── POST /api/plan            # 创建旅行规划
    ├── POST /api/feedback        # 提交反馈
    └── GET  /api/plan/{id}       # 获取当前行程
```

**关键类**:
- `SessionManager`: 会话管理器，支持过期清理

#### 3.1.2 Agent 层 (`backend/agent/`)

**核心类关系**:
```
TripChatSystem（核心系统）
├── llm: ChatOpenAI（DeepSeek）
├── tools: List[Tool]（MCP 工具）
├── graph: StateGraph（LangGraph 执行图）
│
└── initialize() → 加载 MCP 工具，构建执行图

TripChatSession（会话管理）
├── system: TripChatSystem
├── thread_id: str（会话ID）
├── config: dict（LangGraph 配置）
│
├── start(request) → 执行规划
├── feedback(message) → 处理反馈
└── get_current_plan() → 获取当前行程
```

**执行流程**:
```
用户输入
    │
    ▼
┌─────────────────────────────────────────────┐
│            LangGraph 执行图                  │
│                                             │
│  ┌─────────────┐   ┌─────────────┐         │
│  │ 景点专家     │──▶│ 天气专家     │         │
│  │ maps_text_  │   │ maps_weather│         │
│  │ search      │   │             │         │
│  └─────────────┘   └─────────────┘         │
│         │                 │                 │
│         ▼                 ▼                 │
│  attractions_data   weather_data           │
│                                             │
│         ┌─────────────┐                    │
│         │ 酒店专家     │                    │
│         │ maps_text_  │                    │
│         │ search      │                    │
│         └─────────────┘                    │
│                 │                           │
│                 ▼                           │
│          hotels_data                        │
│                 │                           │
│                 ▼                           │
│         ┌─────────────┐                    │
│         │ 行程规划器   │                    │
│         │ LLM + JSON  │                    │
│         └─────────────┘                    │
│                 │                           │
│                 ▼                           │
│           final_plan                        │
└─────────────────────────────────────────────┘
    │
    ▼
TripPlan（结构化输出）
```

#### 3.1.3 状态定义 (`backend/agent/state.py`)

```python
class ChatAgentState(TypedDict):
    # 用户输入
    city: str
    start_date: str
    end_date: str
    interests: List[str]
    accommodation_type: Optional[str]
    budget_per_day: Optional[int]

    # 中间结果（累加）
    attractions_data: Annotated[List[Dict], operator.add]
    weather_data: Annotated[List[Dict], operator.add]
    hotels_data: Annotated[List[Dict], operator.add]

    # 对话相关
    messages: Annotated[List[Dict], operator.add]
    user_feedback: Optional[str]
    intent: Optional[str]

    # 最终结果
    final_plan: Optional[Dict[str, Any]]
    execution_errors: Annotated[List[str], operator.add]
```

#### 3.1.4 节点实现 (`backend/agent/nodes/nodes.py`)

| 节点函数 | 职责 | 工具 |
|----------|------|------|
| `create_attraction_node()` | 搜索景点 | maps_text_search |
| `create_weather_node()` | 查询天气 | maps_weather |
| `create_hotel_node()` | 搜索酒店 | maps_text_search |
| `plan_trip_node()` | 生成行程规划 | LLM only |
| `parse_intent_node()` | 解析用户意图 | LLM only |
| `adjust_plan_node()` | 调整行程 | LLM only |

#### 3.1.5 数据模型 (`backend/model/schemas.py`)

**请求模型**:
```python
class TripRequest(BaseModel):
    city: str
    start_date: str
    end_date: str
    interests: List[str]
    budget_per_day: Optional[int]
    accommodation_type: Optional[str]
    transportation_mode: Optional[str]
```

**响应模型**:
```python
class TripPlan(BaseModel):
    city: str
    start_date: str
    end_date: str
    days: List[DayPlan]
    weather_info: List[WeatherInfo]
    overall_suggestions: str
    budget: Optional[Budget]

class DayPlan(BaseModel):
    date: str
    day_index: int
    description: str
    transportation: str
    accommodation: str
    hotel: Optional[Hotel]
    attractions: List[Attraction]
    meals: List[Meal]
```

#### 3.1.6 配置管理 (`backend/config/settings.py`)

```python
class Settings(BaseSettings):
    # API Keys
    deepseek_api_key: Optional[str] = None
    amap_maps_api_key: Optional[str] = None

    # 应用配置
    app_name: str = "Travel Planning Agent"
    debug: bool = False

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000

    # 会话配置
    session_expire_seconds: int = 3600

    # CORS 配置
    allowed_origins: Optional[List[str]] = None

    # 业务配置
    confirm_keywords: List[str] = ['确认', '满意', '好的', ...]
```

#### 3.1.7 Prompt 定义 (`backend/prompts/__init__.py`)

| Prompt 名称 | 用途 |
|-------------|------|
| `ATTRACTION_AGENT_PROMPT` | 景点专家系统提示词 |
| `WEATHER_AGENT_PROMPT` | 天气专家系统提示词 |
| `HOTEL_AGENT_PROMPT` | 酒店专家系统提示词 |
| `PLANNER_AGENT_PROMPT` | 行程规划器提示词 |
| `INTENT_PARSER_PROMPT` | 意图解析提示词 |
| `ADJUSTMENT_PROMPT` | 行程调整提示词 |

---

### 3.2 前端模块

#### 3.2.1 技术栈

- **框架**: Vue 3（Composition API）
- **语言**: TypeScript
- **构建**: Vite
- **HTTP**: Axios

#### 3.2.2 组件结构

```
App.vue
└── TripPlanner.vue（主业务组件）
    ├── 表单区域
    │   ├── 城市/日期选择
    │   ├── 兴趣偏好输入
    │   └── 可选配置项
    │
    ├── 结果展示
    │   ├── 每日行程卡片
    │   ├── 天气预报
    │   ├── 预算估算
    │   └── 总体建议
    │
    └── 反馈区域
        ├── 文本输入
        └── 快捷反馈按钮
```

#### 3.2.3 API 调用 (`frontend/src/api/index.ts`)

```typescript
export const api = {
  // 创建旅行规划
  async createPlan(request: PlanRequest): Promise<PlanResponse>

  // 提交反馈
  async submitFeedback(request: FeedbackRequest): Promise<FeedbackResponse>

  // 获取当前行程
  async getPlan(sessionId: string): Promise<PlanResponse>
}
```

---

## 四、数据流

### 4.1 请求流程

```
用户输入（前端）
    │
    ▼
POST /api/plan
    │
    ▼
TripChatSession.start(request)
    │
    ▼
LangGraph 执行图
    │
    ├──▶ 景点专家 ──▶ attractions_data
    │
    ├──▶ 天气专家 ──▶ weather_data
    │
    ├──▶ 酒店专家 ──▶ hotels_data
    │
    └──▶ 行程规划器 ──▶ final_plan
                │
                ▼
        TripPlan（结构化输出）
                │
                ▼
        JSON Response ──▶ 前端渲染
```

### 4.2 多轮对话流程

```
用户反馈（前端）
    │
    ▼
POST /api/feedback
    │
    ▼
TripChatSession.feedback(message)
    │
    ├──▶ 解析意图（parse_intent_node）
    │       │
    │       └──▶ intent, target_days, action, details
    │
    └──▶ 调整行程（adjust_plan_node）
            │
            └──▶ 新的 TripPlan
                    │
                    ▼
            JSON Response ──▶ 前端更新
```

---

## 五、依赖清单

### 5.1 后端依赖 (`backend/requirements.txt`)

```
fastapi>=0.104.1
uvicorn>=0.24.0
pydantic>=2.7.4
pydantic-settings>=2.1.0
aiohttp>=3.9.1
python-multipart>=0.0.6
python-dotenv>=1.0.0

# LangChain & LangGraph
langgraph>=0.2.0
langchain-openai>=0.2.0
langchain-mcp-adapters>=0.1.0
langchain-classic>=0.1.0
langchain-core>=0.3.0
```

### 5.2 前端依赖 (`frontend/package.json`)

```json
{
  "dependencies": {
    "axios": "^1.13.6",
    "vue": "^3.5.30"
  },
  "devDependencies": {
    "@types/node": "^24.12.0",
    "@vitejs/plugin-vue": "^6.0.5",
    "@vue/tsconfig": "^0.9.0",
    "typescript": "~5.9.3",
    "vite": "^8.0.1",
    "vue-tsc": "^3.2.5"
  }
}
```

---

## 六、环境配置

### 6.1 环境变量 (`.env`)

```bash
# DeepSeek API 配置
DEEPSEEK_API_KEY=your_deepseek_api_key

# 高德地图 API 配置
AMAP_MAPS_API_KEY=your_amap_api_key

# 应用配置
APP_NAME=Travel Planning Agent
DEBUG=false

# 服务器配置
HOST=0.0.0.0
PORT=8000

# 会话配置（可选）
SESSION_EXPIRE_SECONDS=3600

# CORS 配置（可选，生产环境建议配置）
# ALLOWED_ORIGINS=["https://your-domain.com"]
```

---

## 七、启动命令

### 7.1 后端启动

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 启动开发服务器
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 或直接运行
python -m backend.main
```

### 7.2 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

---

## 八、API 接口

### 8.1 创建旅行规划

**请求**:
```http
POST /api/plan
Content-Type: application/json

{
  "city": "北京",
  "start_date": "2026-03-26",
  "end_date": "2026-03-27",
  "interests": ["历史古迹"],
  "budget_per_day": 500,
  "accommodation_type": "中档酒店"
}
```

**响应**:
```json
{
  "success": true,
  "session_id": "uuid-string",
  "plan": {
    "city": "北京",
    "start_date": "2026-03-26",
    "end_date": "2026-03-27",
    "days": [...],
    "weather_info": [...],
    "budget": {...}
  }
}
```

### 8.2 提交反馈

**请求**:
```http
POST /api/feedback
Content-Type: application/json

{
  "session_id": "uuid-string",
  "message": "第一天景点有点多"
}
```

**响应**:
```json
{
  "success": true,
  "plan": {
    // 调整后的行程
  }
}
```

### 8.3 获取当前行程

**请求**:
```http
GET /api/plan/{session_id}
```

**响应**:
```json
{
  "success": true,
  "plan": {
    // 当前行程
  }
}
```

---

## 九、已知问题与待优化项

| 优先级 | 问题 | 状态 |
|--------|------|------|
| ~~P0~~ | ~~ADJUSTMENT_PROMPT 变量未传入~~ | ✅ 已修复 |
| ~~P0~~ | ~~工具过滤 fallback 逻辑危险~~ | ✅ 已修复 |
| ~~P0~~ | ~~会话存储内存泄漏~~ | ✅ 已修复 |
| ~~P0~~ | ~~CORS 配置 `*` 安全风险~~ | ✅ 已修复 |
| P1 | 添加日志系统 | 待修复 |
| P1 | extract_json_from_text 改进 | 待修复 |
| P2 | 补充 pytest 单元测试 | 待修复 |
| P2 | 类型注解改进 | 待修复 |
| P2 | 前端环境变量配置 | 待修复 |

详细问题清单见: `problem3.md`

---

## 十、扩展方向

### 10.1 短期优化

1. **日志系统**: 集成 Python logging，支持结构化日志和请求追踪
2. **错误处理**: 统一错误码和错误消息格式
3. **单元测试**: pytest + mock 实现单元测试覆盖

### 10.2 中期优化

1. **Redis 会话**: 替换内存存储，支持分布式部署
2. **流式输出**: 支持 SSE/WebSocket 实时返回规划进度
3. **缓存机制**: 缓存景点/天气数据，减少 API 调用

### 10.3 长期规划

1. **多语言支持**: 国际化 i18n
2. **个性化推荐**: 基于用户历史偏好推荐
3. **行程分享**: 生成分享链接或导出 PDF

---

> 文档维护: Claude Code
> 最后更新: 2026-03-30