# 项目架构文档

> 本文档帮助开发者深入理解后端代码框架的设计和实现细节。

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈详解](#2-技术栈详解)
3. [后端目录结构](#3-后端目录结构)
4. [核心架构设计](#4-核心架构设计)
5. [详细模块解析](#5-详细模块解析)
6. [数据流与调用链路](#6-数据流与调用链路)
7. [推荐阅读顺序](#7-推荐阅读顺序)
8. [配置与部署](#8-配置与部署)

---

## 1. 项目概述

### 1.1 项目定位

这是一个**对话式旅行规划 Agent**，用户可以通过自然语言描述旅行需求，系统自动收集信息并生成个性化行程。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| 多轮对话 | 支持持续交互，逐步收集用户需求 |
| 智能需求收集 | 自动识别出发地、目的地、日期等关键信息 |
| 行程规划 | 基于景点、天气、酒店、交通数据生成详细行程 |
| ReAct 推理 | 动态决策模式，支持复杂需求场景 |
| 流式输出 | SSE 实时推送规划进度 |

### 1.3 技术亮点

- **LangGraph 状态机**: 使用有向图编排对话流程，支持条件路由和循环
- **MCP 工具集成**: 统一的工具调用协议，支持高德地图、12306 等外部服务
- **共享资源管理**: 单例模式共享 MCP 连接，新会话创建毫秒级

---

## 2. 技术栈详解

### 2.1 后端框架

```
FastAPI
  ↓
LangGraph (状态编排)
  ↓
LangChain (LLM 抽象 + 工具绑定)
  ↓
MCP (统一工具协议)
```

| 技术 | 作用 | 关键特性 |
|------|------|----------|
| **FastAPI** | 异步 Web 框架 | 支持 SSE、自动 OpenAPI 文档 |
| **LangGraph** | 状态图编排 | 条件路由、循环、状态持久化 |
| **LangChain** | LLM 抽象层 | 工具调用、结构化输出 |
| **MCP** | 工具协议 | 高德地图、12306 等工具统一接口 |
| **MemorySaver** | 状态存储 | 内存持久化，支持会话恢复 |

### 2.2 模型配置

项目使用阿里云 DashScope API（兼容 OpenAI 格式）：

```python
# backend/config/settings.py
class Settings(BaseSettings):
    dashscope_api_key: Optional[str] = None  # 阿里云 API Key
    amap_maps_api_key: Optional[str] = None  # 高德地图 API Key
    primary_model: str = "qwen-plus"          # 主模型
    llm_temperature: float = 0.7              # 温度参数
```

---

## 3. 后端目录结构

```
backend/
├── main.py                 # 【入口】FastAPI 应用，路由定义，会话管理
│
├── agent/                  # 【核心】Agent 模块
│   ├── __init__.py         # 模块导出
│   ├── trip_agent.py       # 会话管理（ChatSession）、共享资源管理器
│   ├── state.py            # 状态定义（ChatAgentState）
│   ├── router.py           # 查询复杂度分析
│   │
│   ├── nodes/              # 节点实现
│   │   ├── nodes.py        # 专家节点、规划节点、对话节点
│   │   └── react_nodes.py  # ReAct 推理节点
│   │
│   ├── graphs/             # 图构建
│   │   └── react_graph.py  # ReAct 图结构
│   │
│   └── tools/              # 工具管理
│       └── mcp_tools.py    # MCP 工具管理器
│
├── config/                 # 【配置】
│   ├── settings.py         # 配置管理（Pydantic Settings）
│   └── mcp_config.json     # MCP 服务器配置
│
├── model/                  # 【数据模型】
│   └── schemas.py          # Pydantic 模型定义
│
├── prompts/                # 【提示词】
│   └── __init__.py         # 所有 Agent Prompt 模板
│
├── evaluation/             # 【评估】
│   └── evaluator.py        # 行程质量评估器
│
├── utils/                  # 【工具函数】
│   └── date_parser.py      # 日期解析
│
└── tests/                  # 【测试】
    ├── unit/               # 单元测试
    ├── integration/        # 集成测试
    └── mocks/              # Mock 对象
```

---

## 4. 核心架构设计

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FastAPI Layer                              │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  main.py                                                        ││
│  │  - SessionManager (会话存储与过期清理)                           ││
│  │  - Routes: /api/chat, /api/chat/stream                          ││
│  │  - SSE Streaming Response                                       ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Session Layer                                │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  ChatSession (trip_agent.py)                                    ││
│  │  - 每个用户独立的会话实例                                        ││
│  │  - chat_graph: 对话流程图                                       ││
│  │  - plan_graph: 规划流程图                                       ││
│  │  - checkpointer: MemorySaver (状态持久化)                       ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  SharedResourceManager (单例)                                   ││
│  │  - 共享 MCP 工具连接                                            ││
│  │  - 共享 LLM 实例                                                ││
│  │  - 新会话创建毫秒级                                              ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Graph Layer                                  │
│                                                                      │
│  ┌───────────────────────┐    ┌───────────────────────┐            │
│  │   Chat Graph          │    │   Plan Graph          │            │
│  │   (对话流程)          │    │   (规划流程)          │            │
│  │                       │    │                       │            │
│  │   analyzer ──► response│    │   Smart / ReAct 模式 │            │
│  └───────────────────────┘    └───────────────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Node Layer                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │  专家节点   │ │  对话节点   │ │  规划节点   │ │  ReAct节点  │   │
│  │             │ │             │ │             │ │             │   │
│  │ - 景点查询  │ │ - 需求分析  │ │ - 行程生成  │ │ - reasoning │   │
│  │ - 天气查询  │ │ - 响应生成  │ │ - 行程调整  │ │ - action    │   │
│  │ - 酒店查询  │ │ - 确认检查  │ │ - 反思评估  │ │ - reflection│   │
│  │ - 交通查询  │ │             │ │             │ │             │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Tool Layer                                  │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  MCP Tools (高德地图, 12306)                                    ││
│  │  - maps_text_search: 景点/酒店搜索                              ││
│  │  - maps_weather: 天气查询                                       ││
│  │  - get-tickets: 火车票查询                                      ││
│  │  - maps_around_search: 周边搜索                                 ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 共享资源管理器（单例模式）

**位置**: `backend/agent/trip_agent.py`

**设计理念**:
- MCP 工具连接是 I/O 操作，初始化需要 60+ 秒
- LLM 实例是无状态的，可以安全共享
- 共享后，新会话创建只需毫秒级

```python
class SharedResourceManager:
    """共享资源管理器 - 全局单例"""

    _instance: Optional['SharedResourceManager'] = None
    _initialized: bool = False

    def __new__(cls):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def ensure_initialized(cls) -> 'SharedResourceManager':
        """确保已初始化，返回实例"""
        instance = cls.get_instance()
        if not cls._initialized:
            await instance.initialize()
        return instance

    async def initialize(self):
        """初始化共享资源（MCP 工具、LLM）"""
        # 1. 初始化 LLM
        self._llm = ChatOpenAI(
            model=settings.primary_model,
            openai_api_key=settings.dashscope_api_key,
            openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        # 2. 初始化高德地图 MCP
        server_config = {
            "amap": {
                "command": "uvx",
                "args": ["amap-mcp-server"],
                "transport": "stdio",
                "env": {"AMAP_MAPS_API_KEY": self._amap_key}
            }
        }
        self._client = MultiServerMCPClient(server_config)
        self._tools = await self._client.get_tools()

        SharedResourceManager._initialized = True

    def get_tools(self) -> List:
        return self._tools

    def get_llm(self) -> ChatOpenAI:
        return self._llm
```

**使用方式**:
```python
# 应用启动时初始化（main.py startup_event）
manager = await SharedResourceManager.ensure_initialized()

# 新会话创建时获取共享资源（毫秒级）
session = ChatSession()
await session.initialize()  # 内部调用 SharedResourceManager
```

### 4.3 两种 Agent 模式对比

| 特性 | Smart 模式 | ReAct 模式 |
|------|-----------|-----------|
| **图结构** | 固定流水线 | 动态推理循环 |
| **工具选择** | 并行执行（景点/天气/交通同时查询） | 按需调用（根据推理决定） |
| **适用场景** | 标准规划需求 | 复杂需求、需要多次迭代 |
| **响应速度** | 更快（并行） | 可能更慢（多轮推理） |
| **图入口** | `create_smart_planning_graph()` | `create_react_agent_graph()` |

**Smart 模式图结构**:
```
tool_selector
    │
    ├──────────┬──────────┐
    ▼          ▼          ▼
attraction  weather  transport   (并行执行)
    │          │          │
    └──────────┴──────────┘
              │
              ▼
        gather_parallel_results
              │
              ▼
          hotel_expert
              │
              ▼
          plan_trip
              │
              ▼
          reflection
              │
        ┌─────┴─────┐
        ▼           ▼
      replan       END
```

**ReAct 模式图结构**:
```
        ┌─────────────────────────────────────────┐
        │                                         │
        ▼                                         │
    reasoning ──► action ──► observation          │
        │                         │               │
        │                         ▼               │
        │                     reflection          │
        │                         │               │
        │              ┌──────────┴──────────┐    │
        │              ▼                     ▼    │
        │         should_continue        END     │
        │              │                        │
        └──────────────┘                        │
```

### 4.4 对话状态流转

用户从问候到完成规划的完整状态流转：

```
greeting (问候)
    │
    ▼
collecting (收集必要信息：出发地、目的地、日期)
    │
    ▼
optional_collecting (引导可选参数：兴趣、预算、住宿类型)
    │
    ▼
confirming (确认是否生成行程)
    │
    ▼
planning (执行规划)
    │
    ▼
refining (展示行程，接收调整反馈)
    │
    ▼
done (完成)
```

**状态字段**:
```python
# backend/agent/state.py
conversation_stage: str  # 当前阶段
collected_info: Dict     # 已收集的旅行信息
missing_fields: List     # 缺失的必要字段
ready_to_plan: bool      # 是否可以开始规划
user_confirmed: bool     # 用户是否确认生成
```

---

## 5. 详细模块解析

### 5.1 FastAPI 入口

**文件**: `backend/main.py`

#### 5.1.1 SessionManager 会话管理器

```python
class SessionManager:
    """会话管理器 - 支持过期清理"""

    def __init__(self, expire_seconds: int = 3600):
        self._sessions: Dict[str, Dict] = {}
        self._expire_seconds = expire_seconds

    async def start_cleanup_task(self):
        """启动后台清理任务（每5分钟检查一次）"""
        while True:
            await asyncio.sleep(300)
            self._cleanup_expired()

    def set(self, session_id: str, session: ChatSession):
        """存储会话"""
        self._sessions[session_id] = {
            'session': session,
            'last_active': time.time()
        }

    def get(self, session_id: str) -> Optional[ChatSession]:
        """获取会话（同时更新活跃时间）"""
        session_data = self._sessions.get(session_id)
        if session_data:
            session_data['last_active'] = time.time()
            return session_data['session']
        return None
```

#### 5.1.2 核心路由定义

```python
# 对话式 API（非流式）
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话式交互 API"""
    # 1. 获取或创建会话
    if request.session_id:
        session = session_manager.get(request.session_id)
    else:
        session = ChatSession()
        await session.initialize(agent_mode=request.agent_mode)
        session_manager.set(session.thread_id, session)

    # 2. 处理用户消息
    result = await session.chat(request.message)

    # 3. 返回响应
    return ChatResponse(
        session_id=session.thread_id,
        reply=result['reply'],
        stage=result['stage'],
        collected_info=result.get('collected_info'),
        plan=result.get('plan')
    )


# 流式对话 API（SSE）
@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话 API - 使用 SSE 实时推送进度"""
    async def generate():
        # ... 会话创建逻辑 ...

        # 发送 SSE 事件
        yield f"event: session\ndata: {json.dumps({'session_id': sid})}\n\n"
        yield f"event: message\ndata: {json.dumps({'content': reply})}\n\n"
        yield f"event: stage\ndata: {json.dumps({'stage': stage})}\n\n"
        yield f"event: plan\ndata: {json.dumps({'plan': plan})}\n\n"
        yield f"event: done\ndata: {json.dumps({})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"}
    )
```

#### 5.1.3 SSE 事件格式

```
event: session
data: {"session_id": "uuid-xxx"}

event: message
data: {"content": "正在为您规划行程..."}

event: stage
data: {"stage": "planning", "collected_info": {...}}

event: plan
data: {"plan": {...}}

event: done
data: {}

event: error
data: {"message": "发生错误"}
```

---

### 5.2 Agent 会话管理

**文件**: `backend/agent/trip_agent.py`

#### 5.2.1 ChatSession 类结构

```python
class ChatSession:
    """对话式会话管理"""

    def __init__(self):
        # 共享资源（从全局管理器获取）
        self.shared_resources: Optional[SharedResourceManager] = None
        self.tools: List = []
        self.llm: Optional[ChatOpenAI] = None

        # 独立资源（每个会话独有）
        self.thread_id = str(uuid.uuid4())
        self.checkpointer = MemorySaver()  # 独立的状态存储
        self.chat_graph = None   # 对话图
        self.plan_graph = None   # 规划图
        self.config = {"configurable": {"thread_id": self.thread_id}}

        self._initialized = False
        self.agent_mode: str = "smart"  # "smart" 或 "react"
```

#### 5.2.2 initialize() 方法

```python
async def initialize(self, agent_mode: str = "smart"):
    """初始化会话 - 使用共享资源"""
    if self._initialized:
        return

    self.agent_mode = agent_mode

    # 获取共享资源（毫秒级）
    self.shared_resources = await SharedResourceManager.ensure_initialized()
    self.tools = self.shared_resources.get_tools()
    self.llm = self.shared_resources.get_llm()

    # 创建独立的 LangGraph（每个会话需要独立的 checkpointer）
    self.chat_graph = self._create_chat_graph()
    self.plan_graph = self._create_plan_graph(agent_mode)

    self._initialized = True
```

#### 5.2.3 chat() 方法核心流程

```python
async def chat(self, user_message: str) -> Dict[str, Any]:
    """处理用户消息，返回回复"""
    await self.initialize()

    # 获取当前状态
    current_state = await self.chat_graph.aget_state(self.config)
    stage = current_state.values.get('conversation_stage', 'greeting')
    collected_info = current_state.values.get('collected_info', {})
    current_plan = current_state.values.get('final_plan')

    # 1. 如果已有行程，处理调整请求
    if current_plan:
        return await self._handle_plan_adjustment(user_message, current_state.values)

    # 2. 处理可选参数引导阶段
    if stage == "optional_collecting":
        return await self._handle_optional_collection(user_message, current_state.values)

    # 3. 检查是否确认生成（支持可选参数补充）
    if stage == "confirming" and current_state.values.get('ready_to_plan'):
        # 使用 LLM 分析用户消息（复用 optional_guidance_node）
        result = await optional_guidance_node(self.llm, {
            **current_state.values,
            "user_feedback": user_message,
        })

        # 检查是否提取到新的可选参数
        new_collected = result.get('collected_info', {})
        if new_collected != collected_info:
            # 用户提供了可选参数，更新状态
            return {"reply": "已记录，现在为您生成行程吗？", ...}

        # 检查是否确认生成
        confirm_result = await confirm_check_node({"user_feedback": user_message})
        if confirm_result == "confirmed":
            return await self._generate_and_return(collected_info, current_state.values)

    # 4. 分析用户消息（调用对话图）
    analyze_input = {
        **current_state.values,
        "user_feedback": user_message,
        "collected_info": collected_info,
    }
    result = await self.chat_graph.ainvoke(analyze_input, self.config)

    # 5. 构建响应
    new_state = await self.chat_graph.aget_state(self.config)
    return self._build_response(new_state.values)
```

#### 5.2.4 _generate_and_return() 规划触发

```python
async def _generate_and_return(self, collected_info: Dict, current_values: Dict):
    """生成行程并返回结果"""
    # 1. 构建规划输入
    plan_input = {
        "origin": collected_info.get('origin', ''),
        "city": collected_info.get('city', ''),
        "start_date": collected_info.get('start_date', ''),
        "end_date": collected_info.get('end_date', ''),
        "interests": collected_info.get('interests', []),
        # ... 其他字段 ...
        "conversation_stage": "planning",
        "ready_to_plan": True,
        "user_confirmed": True,
    }

    # 2. 执行规划图
    plan_result = await self.plan_graph.ainvoke(plan_input)
    final_plan = plan_result.get('final_plan')

    # 3. 更新对话状态
    await self.chat_graph.aupdate_state(
        self.config,
        {
            "final_plan": final_plan,
            "conversation_stage": "refining",
        }
    )

    return {
        "reply": "行程已生成！您可以查看并提出调整建议。",
        "stage": "refining",
        "plan": final_plan
    }
```

---

### 5.3 状态定义

**文件**: `backend/agent/state.py`

#### 5.3.1 ChatAgentState TypedDict 结构

```python
class ChatAgentState(TypedDict):
    """多轮对话状态 - 支持持续性交互"""

    # ==================== 用户输入信息 ====================
    origin: str                                   # 出发城市（必要字段）
    city: str                                     # 目标城市
    start_date: str                               # 开始日期 YYYY-MM-DD
    end_date: str                                 # 结束日期 YYYY-MM-DD
    interests: List[str]                          # 兴趣偏好
    accommodation_type: Optional[str]             # 住宿类型
    budget_per_day: Optional[int]                 # 每日预算
    transportation_mode: Optional[str]            # 交通方式

    # ==================== 中间结果 (累加) ====================
    attractions_data: Annotated[List[Dict], operator.add]    # 景点数据
    weather_data: Annotated[List[Dict], operator.add]        # 天气数据
    hotels_data: Annotated[List[Dict], operator.add]         # 酒店数据
    transport_data: Annotated[List[Dict], operator.add]      # 交通数据

    # ==================== 对话相关 ====================
    messages: Annotated[List[Dict], operator.add]  # 对话历史
    user_feedback: Optional[str]                    # 用户最新反馈
    intent: Optional[str]                           # 解析出的意图

    # ==================== 需求收集状态 ====================
    conversation_stage: str           # 对话阶段
    collected_info: Dict[str, Any]    # 已收集的旅行信息
    missing_fields: List[str]         # 缺失的必要字段
    ready_to_plan: bool               # 是否可以开始规划
    user_confirmed: bool              # 用户是否确认生成

    # ==================== Agent 智能决策 ====================
    tool_decisions: Optional[Dict[str, bool]]   # 工具选择决策
    special_instructions: Optional[Dict]        # 用户特别说明

    # ==================== ReAct 思考链 ====================
    thoughts: List[Dict[str, Any]]    # 思考历史
    next_action: str                  # 下一步行动
    should_continue: bool             # 是否继续推理
    quality_score: float              # 当前质量分数

    # ==================== 最终结果 ====================
    final_plan: Optional[Dict[str, Any]]  # 最终行程
    bot_reply: Optional[str]               # 机器人回复
```

#### 5.3.2 必要字段 vs 可选字段

```python
# 必要字段（必须收集完整才能生成行程）
REQUIRED_FIELDS = ['origin', 'city', 'start_date', 'end_date']

# 可选字段（可以引导但不是必须）
# - interests: 兴趣偏好
# - budget_per_day: 每日预算
# - accommodation_type: 住宿类型
# - transportation_mode: 交通方式
```

#### 5.3.3 create_initial_state() 函数

```python
def create_initial_state(request=None) -> Dict[str, Any]:
    """创建初始状态"""
    if request:
        # 表单模式：已有完整信息
        return {
            "city": request.city,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "conversation_stage": "planning",
            "ready_to_plan": True,
            # ... 其他字段 ...
        }
    else:
        # 对话模式：从问候开始
        return {
            "city": "",
            "start_date": "",
            "end_date": "",
            "conversation_stage": "greeting",
            "missing_fields": REQUIRED_FIELDS.copy(),
            "ready_to_plan": False,
            # ... 其他字段 ...
        }
```

---

### 5.4 专家节点

**文件**: `backend/agent/nodes/nodes.py`

#### 5.4.1 create_expert_node 工厂函数

```python
def create_expert_node(
    llm,
    tools,
    system_prompt: str,
    node_name: str,
    prepare_input: Callable[[ChatAgentState], str],
    output_key: str,
    enable_detail_enrich: bool = True
):
    """创建专家节点

    Args:
        llm: 语言模型
        tools: 工具列表
        system_prompt: 系统提示词
        node_name: 节点名称
        prepare_input: 输入准备函数
        output_key: 输出状态键名
        enable_detail_enrich: 是否启用 POI 详情增强

    Returns:
        异步节点函数
    """
    # 1. 过滤出该专家需要的特定工具
    tool_name_map = {t.name: t for t in tools}

    # 2. 创建 Agent
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, filtered_tools, prompt)
    executor = AgentExecutor(agent=agent, tools=filtered_tools)

    # 3. 定义节点函数
    async def node(state: ChatAgentState) -> Dict[str, Any]:
        input_str = prepare_input(state)
        result = await executor.ainvoke({"input": input_str})

        # 提取 JSON 数据
        structured_data = extract_json_from_text(result.get('output', ''))

        # POI 详情增强（景点/酒店）
        if enable_detail_enrich and detail_tool:
            structured_data = await enrich_poi_details(structured_data, detail_tool)

        return {output_key: structured_data}

    return node
```

#### 5.4.2 景点节点实现

```python
def create_attraction_node(llm, tools):
    """创建景点专家节点"""
    return create_expert_node(
        llm=llm,
        tools=tools,
        system_prompt=ATTRACTION_AGENT_PROMPT,
        node_name="景点专家",
        prepare_input=lambda s: f"""请搜索 {s['city']} 的景点，用户兴趣: {s['interests']}。

步骤:
1. 调用 maps_text_search 工具搜索景点
2. 将结果整理成 JSON 数组输出""",
        output_key="attractions_data"
    )
```

#### 5.4.3 智能工具选择器

```python
async def tool_selector_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """智能工具选择器 - 使用 LLM 决定需要调用哪些工具

    这是 Agent 智能化的核心：
    - 首先检查 special_instructions（用户明确表达的跳过意图）
    - 然后使用 LLM 进行补充决策
    - 支持用户说"不看景点"、"已订好酒店"等场景
    """
    # 1. 检查用户特别说明
    special_instructions = state.get('special_instructions', {})

    # 默认工具决策
    tool_decisions = {
        "attraction": True,
        "weather": True,
        "transport": True,
        "hotel": True
    }

    # 2. 根据特别说明跳过工具
    if special_instructions.get('skip_attraction'):
        tool_decisions['attraction'] = False
        print(f"跳过景点查询: {special_instructions.get('skip_attraction_reason')}")

    if special_instructions.get('skip_hotel'):
        tool_decisions['hotel'] = False

    # ... 其他跳过逻辑 ...

    # 3. 使用 LLM 进行补充决策
    if not all_decided:
        response = await llm.ainvoke(prompt)
        llm_decisions = parse_json_response(response.content)
        tool_decisions.update(llm_decisions)

    return {"tool_decisions": tool_decisions}
```

---

### 5.5 ReAct 推理循环

**文件**: `backend/agent/nodes/react_nodes.py`

#### 5.5.1 reasoning_node 推理节点

```python
async def reasoning_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """推理节点 - Agent 思考下一步该做什么

    这是真正的智能核心：
    1. 分析当前状态
    2. 评估已有信息
    3. 决定下一步行动
    4. 给出决策理由
    """
    thoughts = state.get('thoughts', [])
    step = len(thoughts) + 1
    iteration_count = state.get('iteration_count', 0)

    # 防止无限循环
    if iteration_count >= 10:
        return {'next_action': 'finish', 'should_continue': False}

    # 构建上下文
    context = _build_reasoning_context(state)

    prompt = f"""你是一个旅行规划 Agent。请分析当前情况并决定下一步行动。

## 当前状态
{context}

## 可用行动
- query_attraction: 查询景点信息
- query_weather: 查询天气预报
- query_hotel: 查询酒店信息
- query_transport: 查询交通信息
- generate_plan: 生成行程计划
- evaluate_plan: 评估行程质量
- refine_plan: 优化行程
- finish: 完成任务

## 输出格式 (JSON)
{{
    "thought": "分析当前状态...",
    "action": "选择的行动",
    "action_reason": "选择原因",
    "confidence": 0.8,
    "should_continue": true
}}
"""

    response = await llm.ainvoke(prompt)
    result = _parse_json_response(response.content)

    # 记录思考
    new_thought = {
        'step': step,
        'thought': result.get('thought', ''),
        'action': result.get('action', ''),
        'observation': '',  # 行动后填充
        'reflection': '',   # 观察后填充
        'confidence': result.get('confidence', 0.5)
    }

    return {
        'thoughts': thoughts + [new_thought],
        'next_action': result.get('action'),
        'should_continue': result.get('should_continue', True),
        'iteration_count': iteration_count + 1,
    }
```

#### 5.5.2 action_node 行动节点

```python
async def action_node(llm, tools: List, state: ChatAgentState) -> Dict[str, Any]:
    """行动节点 - 执行推理决定的行动"""
    action = state.get('next_action', 'finish')

    # 行动处理器映射
    action_handlers = {
        'query_attraction': lambda: _handle_query_attraction(llm, tools, state),
        'query_weather': lambda: _handle_query_weather(llm, tools, state),
        'query_hotel': lambda: _handle_query_hotel(llm, tools, state),
        'query_transport': lambda: _handle_query_transport(llm, tools, state),
        'generate_plan': lambda: _handle_generate_plan(llm, state),
        'evaluate_plan': lambda: _handle_evaluate_plan(llm, state),
        'refine_plan': lambda: _handle_refine_plan(llm, state),
        'finish': lambda: {}
    }

    handler = action_handlers.get(action)
    if handler:
        return await handler()
    return {}
```

#### 5.5.3 reflection_node 反思节点

```python
async def reflection_node(llm, state: ChatAgentState) -> Dict[str, Any]:
    """反思节点 - 决定是否需要继续推理"""
    thoughts = state.get('thoughts', [])
    final_plan = state.get('final_plan')

    prompt = f"""请反思当前进度并决定是否需要继续。

## 已完成的思考链
{_format_thoughts_summary(thoughts)}

## 当前数据状态
- 景点: {len(state.get('attractions_data', []))} 个
- 天气: {len(state.get('weather_data', []))} 条
- 酒店: {len(state.get('hotels_data', []))} 家
- 行程: {'已生成' if final_plan else '未生成'}

## 输出格式 (JSON)
{{
    "reflection": "反思内容...",
    "quality_score": 0.7,
    "should_continue": false
}}
"""

    response = await llm.ainvoke(prompt)
    result = _parse_json_response(response.content)

    # 更新最后一条思考记录的 reflection
    if thoughts:
        thoughts[-1] = {**thoughts[-1], 'reflection': result.get('reflection', '')}

    return {
        'thoughts': thoughts,
        'should_continue': result.get('should_continue', False),
        'quality_score': result.get('quality_score', 0.5),
    }
```

---

### 5.6 ReAct 图构建

**文件**: `backend/agent/graphs/react_graph.py`

#### 5.6.1 图结构设计

```python
def create_react_agent_graph(llm, tools: List):
    """创建 ReAct Agent 图"""
    workflow = StateGraph(ChatAgentState)

    # === 添加节点 ===
    workflow.add_node("reasoning", reasoning_node)
    workflow.add_node("action", action_node)
    workflow.add_node("observation", observation_node)
    workflow.add_node("reflection", reflection_node)

    # === 设置入口 ===
    workflow.set_entry_point("reasoning")

    # === 添加边 ===
    workflow.add_edge("reasoning", "action")
    workflow.add_edge("action", "observation")
    workflow.add_edge("observation", "reflection")

    # === 条件路由 ===
    def should_continue(state: ChatAgentState) -> str:
        """决定是否继续 ReAct 循环"""
        if state.get('iteration_count', 0) >= 10:
            return "end"
        if state.get('next_action') == 'finish':
            return "end"
        if state.get('quality_score', 0) >= 0.8:
            return "end"
        return "continue"

    workflow.add_conditional_edges(
        "reflection",
        should_continue,
        {"continue": "reasoning", "end": END}
    )

    return workflow.compile()
```

---

### 5.7 工具管理

**文件**: `backend/agent/tools/mcp_tools.py`

#### 5.7.1 MCPToolManager 类

```python
class MCPToolManager:
    """MCP 工具管理器 - 管理所有 MCP 服务器连接"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or settings.mcp_config_path
        self.mcp_servers: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self) -> bool:
        """初始化所有 MCP 服务器连接"""
        # 读取配置文件
        with open(config_full_path, 'r') as f:
            config = json.load(f)

        for server_conf in config.get("mcp_servers", []):
            name = server_conf.get("name")
            url = server_conf.get("url", "")

            if not server_conf.get("enabled"):
                continue

            try:
                # 使用 SSE 连接 MCP 服务器
                server = await self.exit_stack.enter_async_context(
                    MCPServerSse(name=name, params={"url": url})
                )
                self.mcp_servers[name] = server
                print(f"[MCP] 连接成功: {name}")
            except Exception as e:
                print(f"[MCP] 连接失败 {name}: {str(e)}")

        self._initialized = True
        return len(self.mcp_servers) > 0

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        max_retries: int = 2,
        timeout: float = 60.0,
        **kwargs
    ) -> str:
        """调用 MCP 工具，带重试机制"""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self.mcp_servers[server_name].call_tool(tool_name, arguments=kwargs),
                    timeout=timeout
                )
                return self._parse_mcp_result(result)
            except asyncio.TimeoutError:
                print(f"[MCP] {server_name}.{tool_name} 超时")
                if attempt < max_retries:
                    await asyncio.sleep(1 * attempt)  # 指数退避
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    continue

        return json.dumps({"error": f"工具调用失败: {str(last_error)}"})
```

---

### 5.8 行程评估

**文件**: `backend/evaluation/evaluator.py`

#### 5.8.1 PlanMetrics 指标体系

```python
@dataclass
class PlanMetrics:
    """行程评估指标"""

    # 完整性指标 (0-1)
    completeness_score: float = 0.0

    # 合理性指标 (0-1)
    time_efficiency: float = 0.0      # 时间安排合理性
    route_optimality: float = 0.0     # 路线最优性
    budget_accuracy: float = 0.0      # 预算准确性

    # 详细信息
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # 总分 (0-1)
    overall_score: float = 0.0
```

#### 5.8.2 should_replan() 决策逻辑

```python
def should_replan(self, metrics: PlanMetrics, iteration: int = 0) -> Tuple[bool, str]:
    """判断是否需要重新规划"""
    # 防止无限循环：最多重规划3次
    if iteration >= 3:
        return False, "已达到最大重规划次数"

    # 完整性太低，必须重规划
    if metrics.completeness_score < 0.5:
        return True, "行程信息不完整，需要补充查询"

    # 时间安排严重不合理
    if metrics.time_efficiency < 0.3:
        return True, "时间安排严重不合理，需要重新规划"

    # 总分太低
    if metrics.overall_score < 0.5:
        return True, f"行程质量不达标（得分：{metrics.overall_score:.2f}）"

    return False, "规划质量可接受"
```

---

## 6. 数据流与调用链路

### 6.1 用户发送消息的完整流程

```
用户输入
    │
    ▼
FastAPI (/api/chat/stream)
    │
    ▼
SessionManager.get_or_create()
    │
    ├── 存在 → 返回已有会话
    └── 不存在 → ChatSession() + initialize()
    │
    ▼
session.chat(message)
    │
    ▼
chat_graph.aget_state()  # 获取当前状态
    │
    ▼
判断当前阶段
    │
    ├── 已有行程 → _handle_plan_adjustment()
    ├── optional_collecting → _handle_optional_collection()
    ├── confirming + ready → _generate_and_return()
    └── 其他 → chat_graph.ainvoke()
    │
    ▼
return {reply, stage, plan}
    │
    ▼
SSE 流式输出
```

### 6.2 行程生成的完整流程

```
_generate_and_return()
    │
    ▼
构建 plan_input
    │
    ▼
plan_graph.ainvoke(plan_input)
    │
    ▼
tool_selector_node
    │
    ├── attraction: True → attraction_expert (并行)
    ├── weather: True → weather_expert (并行)
    ├── transport: True → transport_expert (并行)
    └── hotel: True → hotel_expert (串行，依赖景点坐标)
    │
    ▼
gather_parallel_results  # 等待并行完成
    │
    ▼
hotel_expert  # 使用景点周边搜索
    │
    ▼
plan_trip_node  # 生成行程
    │
    ▼
reflection_node  # 评估质量
    │
    ├── need_replan=True + iteration<3 → replan_node → 回到 tool_selector
    └── need_replan=False → 返回 final_plan
    │
    ▼
返回结果
```

### 6.3 ReAct 模式的推理流程

```
用户需求
    │
    ▼
reasoning_node
    │
    ├── thought: "缺少景点信息"
    ├── action: "query_attraction"
    └── confidence: 0.8
    │
    ▼
action_node
    │
    └── 调用 create_attraction_node
    │
    ▼
observation_node
    │
    └── observation: "查询到5个景点"
    │
    ▼
reflection_node
    │
    ├── reflection: "景点信息充足"
    ├── quality_score: 0.6
    └── should_continue: True
    │
    ▼
should_continue?
    │
    ├── True → 回到 reasoning_node
    └── False → 返回 final_plan
    │
    ▼
下一轮推理...
    │
    ├── reasoning_node → action: "query_weather"
    ├── action_node → 查询天气
    ├── observation_node → 观察结果
    └── reflection_node → quality_score: 0.8
    │
    ▼
继续推理...
    │
    ├── reasoning_node → action: "generate_plan"
    ├── action_node → 生成行程
    ├── observation_node → 行程已生成
    └── reflection_node → quality_score: 0.85, should_continue: False
    │
    ▼
END
```

---

## 7. 推荐阅读顺序

### 第一阶段：理解入口和数据流

1. **`backend/main.py`** - 理解 FastAPI 入口和会话管理
   - 重点：SessionManager, chat() 和 chat_stream() 路由

2. **`backend/agent/state.py`** - 理解状态数据结构
   - 重点：ChatAgentState TypedDict, REQUIRED_FIELDS

### 第二阶段：理解会话管理

3. **`backend/agent/trip_agent.py`** - 理解会话管理和共享资源
   - 重点：SharedResourceManager, ChatSession, chat() 方法

### 第三阶段：理解对话流程

4. **`backend/agent/nodes/nodes.py`**（对话节点部分）
   - 重点：greeting_node, requirement_analyzer_node, response_generator_node
   - 理解需求收集和阶段流转

### 第四阶段：理解规划流程

5. **`backend/agent/nodes/nodes.py`**（规划节点部分）
   - 重点：create_expert_node, create_smart_planning_graph
   - 理解专家节点和规划图

### 第五阶段：理解 ReAct 模式

6. **`backend/agent/nodes/react_nodes.py`**
   - 重点：reasoning_node, action_node, reflection_node

7. **`backend/agent/graphs/react_graph.py`**
   - 重点：create_react_agent_graph, should_continue 路由

### 第六阶段：理解工具和评估

8. **`backend/agent/tools/mcp_tools.py`** - 理解 MCP 工具管理
9. **`backend/evaluation/evaluator.py`** - 理解行程评估

---

## 8. 配置与部署

### 8.1 环境变量配置

创建 `.env` 文件：

```env
# 阿里云 DashScope API Key（用于 LLM）
DASHSCOPE_API_KEY=sk-xxx

# 高德地图 API Key
AMAP_MAPS_API_KEY=xxx

# 模型配置
PRIMARY_MODEL=qwen-plus
LLM_TEMPERATURE=0.7

# 调试模式
DEBUG=false
```

### 8.2 启动命令

```bash
# 开发模式
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 8.3 API 文档

启动后访问：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 附录：关键文件速查表

| 功能 | 文件路径 |
|------|----------|
| API 入口 | `backend/main.py` |
| 会话管理 | `backend/agent/trip_agent.py` |
| 状态定义 | `backend/agent/state.py` |
| 专家节点 | `backend/agent/nodes/nodes.py` |
| ReAct 节点 | `backend/agent/nodes/react_nodes.py` |
| ReAct 图 | `backend/agent/graphs/react_graph.py` |
| 工具管理 | `backend/agent/tools/mcp_tools.py` |
| 数据模型 | `backend/model/schemas.py` |
| Prompt 模板 | `backend/prompts/__init__.py` |
| 配置管理 | `backend/config/settings.py` |
| 行程评估 | `backend/evaluation/evaluator.py` |