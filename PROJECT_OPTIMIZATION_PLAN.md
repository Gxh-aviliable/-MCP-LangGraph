# 项目优化计划书

> 基于 2025 年暑期实习大模型应用岗位要求的项目差距分析

---

## 目录

1. [核心问题（致命伤）](#一核心问题致命伤)
2. [架构设计问题](#二架构设计问题)
3. [工程实践问题](#三工程实践问题)
4. [执行计划](#四执行计划)
5. [面试定位建议](#五面试定位建议)

---

## 一、核心问题（致命伤）

### 1.1 没有真正的 Agent "智能"

**问题描述：**

当前的"专家节点"本质上是固定流程编排，不是真正的 Agent 推理。

```python
# 当前实现：硬编码的流水线
workflow.add_edge("attraction_expert", "weather_expert")
workflow.add_edge("weather_expert", "transport_expert")
workflow.add_edge("transport_expert", "hotel_expert")
```

**问题表现：**
- 用户说"我只关心美食，不看景点"，系统还是会去查景点
- 用户说"我已经订好酒店了"，系统还是会去查酒店
- 没有动态规划、没有自我反思、没有工具选择的推理过程

**面试官会问：** "你这个和 if-else 有什么区别？Agent 的智能体现在哪？"

**解决方案：**

引入条件路由 + LLM 决策机制：

```python
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage

async def should_query_attraction(state: ChatAgentState) -> str:
    """LLM 决定是否需要查询景点"""
    decision_prompt = f"""
    用户需求：{state.get('collected_info', {})}
    已有信息：{state.get('collected_info', {}).get('interests', [])}

    请判断是否需要查询景点信息？
    - 如果用户明确说"不看景点"，返回 skip
    - 如果用户说"美食为主"，返回 skip
    - 否则返回 query
    """
    decision = await llm.ainvoke(decision_prompt)
    return "skip" if "skip" in decision.lower() else "query"

# 使用条件路由
workflow.add_conditional_edges(
    "analyzer",
    should_query_attraction,
    {"query": "attraction_expert", "skip": "weather_expert"}
)
```

**优化目标：** Agent 能根据用户意图动态决定调用哪些工具，而非固定流程。

---

### 1.2 没有 RAG / 长期记忆

**问题描述：**

整个系统依赖外部 API，零知识沉淀。

| 场景 | 当前表现 | 期望表现 |
|------|---------|---------|
| 用户问"北京有什么小众景点" | ❌ 无法回答，只能通过 API 搜索热门景点 | ✅ 从知识库检索小众景点推荐 |
| 用户第二次来 | ❌ 完全不记得上次偏好 | ✅ 记住"喜欢历史古迹""预算中档" |
| 同一城市多次规划 | ❌ 每次重新查询，无积累 | ✅ 缓存知识，响应更快 |

**这是大模型应用的核心技能，完全缺失。**

**解决方案：**

引入向量数据库 + RAG 检索增强：

```
项目结构变更：
backend/
├── rag/
│   ├── __init__.py
│   ├── embeddings.py      # Embedding 模型配置
│   ├── vectorstore.py     # 向量数据库（ChromaDB/FAISS）
│   ├── knowledge_base.py  # 知识库管理
│   └── retriever.py       # 检索器
├── data/
│   └── knowledge/
│       ├── attractions.json    # 景点知识库
│       ├── travel_tips.json    # 旅行攻略
│       └── user_preferences/   # 用户偏好存储
```

**核心代码示例：**

```python
# backend/rag/retriever.py
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import DashScopeEmbeddings

class TravelKnowledgeRetriever:
    def __init__(self):
        self.embeddings = DashScopeEmbeddings(
            model="text-embedding-v2",
            dashscope_api_key=settings.dashscope_api_key
        )
        self.vectorstore = Chroma(
            persist_directory="backend/data/travel_vectordb",
            embedding_function=self.embeddings
        )

    async def search_attractions(self, query: str, city: str, k: int = 5):
        """检索景点知识"""
        results = self.vectorstore.similarity_search(
            query=f"{city} {query}",
            k=k,
            filter={"type": "attraction", "city": city}
        )
        return results

    async def save_user_preference(self, session_id: str, preferences: dict):
        """保存用户偏好到向量库"""
        # 将用户偏好转为向量存储
        pass
```

**优化目标：**
1. 景点知识库：存储北京 100+ 景点的详细信息
2. 用户记忆：记住每个用户的旅行偏好
3. 攻略知识：存储旅行攻略、美食推荐等

---

### 1.3 对话理解太浅

**问题描述：**

需求收集靠的是 LLM 提取 JSON，不是系统性的对话状态管理。

**问题表现：**
- 用户说"下周想去北京玩几天" → 无法理解"下周"是具体哪天
- 用户说"预算两千左右" → 无法处理模糊表达
- 用户中途改口"不对，我要去上海" → 状态更新不完整

**解决方案：**

实现系统性的对话状态管理：

```python
# backend/agent/dialogue_manager.py
from enum import Enum
from typing import Optional, Dict, Any

class DialogueState(Enum):
    GREETING = "greeting"
    COLLECTING_ORIGIN = "collecting_origin"
    COLLECTING_DESTINATION = "collecting_destination"
    COLLECTING_DATES = "collecting_dates"
    COLLECTING_PREFERENCES = "collecting_preferences"
    CONFIRMING = "confirming"
    PLANNING = "planning"
    REFINING = "refining"

class DialogueManager:
    """对话状态机管理器"""

    def __init__(self):
        self.state_transitions = {
            DialogueState.GREETING: [DialogueState.COLLECTING_ORIGIN],
            DialogueState.COLLECTING_ORIGIN: [DialogueState.COLLECTING_DESTINATION],
            # ... 状态转移表
        }

    async def process_message(self, message: str, current_state: DialogueState, context: dict):
        """处理消息，更新状态"""
        # 1. 意图识别
        intent = await self._recognize_intent(message)

        # 2. 槽位填充
        slots = await self._fill_slots(message, context)

        # 3. 状态转移
        next_state = self._get_next_state(current_state, intent, slots)

        # 4. 生成回复
        response = await self._generate_response(next_state, slots)

        return next_state, slots, response

    async def _recognize_intent(self, message: str) -> str:
        """意图识别"""
        prompt = f"""
        分析用户意图，从以下选项中选择：
        - provide_origin: 提供出发地
        - provide_destination: 提供目的地
        - provide_dates: 提供日期
        - modify_info: 修改已提供信息
        - confirm: 确认生成
        - cancel: 取消

        用户消息：{message}
        """
        return await self.llm.ainvoke(prompt)

    async def _fill_slots(self, message: str, context: dict) -> dict:
        """槽位填充 - 支持模糊表达"""
        # 相对日期解析
        if "下周" in message:
            next_monday = self._get_next_monday()
            context["start_date"] = next_monday

        # 模糊预算解析
        if "两千左右" in message:
            context["budget"] = 2000
            context["budget_flexible"] = True

        return context
```

**优化目标：**
1. 完整的对话状态机
2. 相对日期解析（下周、下个月、五一假期）
3. 模糊表达处理（两千左右、玩几天）
4. 中途修改支持

---

## 二、架构设计问题

### 2.1 LangGraph 用法不规范

**问题描述：**

```python
# 当前问题：所有节点都在一个 graph 里，职责不清
workflow.add_node("attraction_expert", create_attraction_node(...))
workflow.add_node("weather_expert", create_weather_expert(...))
# ... 硬编码连接
```

**解决方案：**

采用分层架构 + 子图模式：

```python
# backend/agent/graphs/
# ├── requirement_graph.py    # 需求收集子图
# ├── planning_graph.py       # 行程规划子图
# └── main_graph.py           # 主图（协调器）

# backend/agent/graphs/requirement_graph.py
def create_requirement_graph():
    """需求收集子图"""
    workflow = StateGraph(RequirementState)

    workflow.add_node("intent_parser", parse_intent)
    workflow.add_node("slot_filler", fill_slots)
    workflow.add_node("validator", validate_info)

    workflow.add_edge("intent_parser", "slot_filler")
    workflow.add_conditional_edges("slot_filler", should_confirm)

    return workflow.compile()

# backend/agent/graphs/planning_graph.py
def create_planning_graph():
    """行程规划子图 - 支持动态工具选择"""
    workflow = StateGraph(PlanningState)

    # 工具选择决策节点
    workflow.add_node("tool_selector", select_tools)
    workflow.add_node("attraction_query", query_attractions)
    workflow.add_node("weather_query", query_weather)
    # ...

    # 条件路由：根据用户需求选择调用的工具
    workflow.add_conditional_edges(
        "tool_selector",
        route_to_tools,
        {
            "attraction": "attraction_query",
            "weather": "weather_query",
            "skip": "planner"
        }
    )

    return workflow.compile()
```

---

### 2.2 工具管理混乱

**问题描述：**

```python
# 问题1：运行时动态获取工具，可能失败
train_tools = await mcp_client.get_tools(server_name="12306 Server")

# 问题2：MCP 协议不稳定，没有降级方案
# 问题3：工具和 Agent 耦合太紧
```

**解决方案：**

实现工具注册中心 + 降级机制：

```python
# backend/agent/tools/tool_registry.py
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

class ToolStatus(Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"  # 降级模式
    UNAVAILABLE = "unavailable"

@dataclass
class ToolInfo:
    name: str
    description: str
    func: Callable
    status: ToolStatus
    fallback: Optional[Callable] = None
    mcp_server: Optional[str] = None

class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}
        self._mcp_tools: List = []

    def register(self, tool_info: ToolInfo):
        """注册工具"""
        self._tools[tool_info.name] = tool_info

    async def get_tool(self, name: str) -> Optional[Callable]:
        """获取工具（带降级）"""
        tool = self._tools.get(name)
        if not tool:
            return None

        if tool.status == ToolStatus.AVAILABLE:
            return tool.func
        elif tool.status == ToolStatus.DEGRADED and tool.fallback:
            print(f"[Tool] {name} 降级模式，使用备用方案")
            return tool.fallback
        else:
            return None

    async def call_tool(self, name: str, **kwargs):
        """调用工具（带重试和降级）"""
        tool = await self.get_tool(name)
        if not tool:
            raise ToolNotAvailableError(f"工具 {name} 不可用")

        try:
            return await tool(**kwargs)
        except Exception as e:
            # 尝试降级
            tool_info = self._tools.get(name)
            if tool_info and tool_info.fallback:
                print(f"[Tool] {name} 调用失败，使用降级方案: {e}")
                return await tool_info.fallback(**kwargs)
            raise

# 工具降级示例
def register_train_tool(registry: ToolRegistry):
    """注册火车票工具（带降级）"""
    registry.register(ToolInfo(
        name="query_train_tickets",
        description="查询火车票",
        func=mcp_train_query,  # MCP 工具
        status=ToolStatus.AVAILABLE,
        fallback=fallback_train_query,  # 降级方案：调用本地 API 或返回提示
        mcp_server="12306"
    ))

async def fallback_train_query(origin: str, destination: str, date: str):
    """火车票查询降级方案"""
    # 方案1：调用备用 API
    # 方案2：返回提示让用户自行查询
    return {
        "status": "degraded",
        "message": "火车票查询服务暂时不可用，请前往 12306 官网查询",
        "url": f"https://www.12306.cn/index/?from={origin}&to={destination}"
    }
```

---

### 2.3 没有评估体系

**问题描述：**

```
- 没有评估指标：行程质量怎么衡量？
- 没有测试集：无法回归测试
- 没有 tracing：Agent 决策过程不可追溯
```

**解决方案：**

建立完整的评估体系：

```python
# backend/evaluation/
# ├── __init__.py
# ├── metrics.py         # 评估指标
# ├── test_cases.py      # 测试用例
# └── evaluator.py       # 评估器

# backend/evaluation/metrics.py
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class PlanMetrics:
    """行程规划评估指标"""

    # 完整性指标
    completeness_score: float  # 必要信息完整度 (0-1)

    # 合理性指标
    time_efficiency: float     # 时间安排合理性 (0-1)
    route_optimality: float    # 路线最优性 (0-1)
    budget_accuracy: float     # 预算准确性 (0-1)

    # 用户体验指标
    attraction_diversity: float  # 景点多样性
    meal_appropriateness: float  # 餐饮安排合理性

    # 总分
    overall_score: float

class PlanEvaluator:
    """行程评估器"""

    def evaluate(self, plan: Dict[str, Any], requirements: Dict[str, Any]) -> PlanMetrics:
        """评估行程质量"""

        # 1. 完整性检查
        completeness = self._check_completeness(plan)

        # 2. 时间合理性检查
        time_eff = self._check_time_efficiency(plan)

        # 3. 路线最优性
        route_opt = self._check_route_optimality(plan)

        # 4. 预算准确性
        budget_acc = self._check_budget_accuracy(plan, requirements)

        # 5. 计算总分
        overall = (completeness * 0.3 + time_eff * 0.25 +
                   route_opt * 0.25 + budget_acc * 0.2)

        return PlanMetrics(
            completeness_score=completeness,
            time_efficiency=time_eff,
            route_optimality=route_opt,
            budget_accuracy=budget_acc,
            overall_score=overall
        )

    def _check_completeness(self, plan: Dict) -> float:
        """检查行程完整性"""
        required_fields = ['days', 'transport_options', 'weather_info', 'budget']
        present = sum(1 for f in required_fields if f in plan and plan[f])
        return present / len(required_fields)

    def _check_time_efficiency(self, plan: Dict) -> float:
        """检查时间安排合理性"""
        score = 1.0
        for day in plan.get('days', []):
            attractions = day.get('attractions', [])
            # 每天景点数量合理性 (2-4个最佳)
            if len(attractions) < 2:
                score -= 0.1  # 太少
            elif len(attractions) > 5:
                score -= 0.15  # 太多
        return max(0, score)

# backend/evaluation/test_cases.py
TEST_CASES = [
    {
        "name": "基础行程规划",
        "input": {
            "origin": "上海",
            "city": "北京",
            "start_date": "2025-07-01",
            "end_date": "2025-07-03",
            "interests": ["历史古迹"]
        },
        "expected": {
            "min_days": 3,
            "must_have_attractions": ["故宫", "天安门"],
            "max_budget_per_day": 1000
        }
    },
    {
        "name": "美食主题行程",
        "input": {
            "origin": "广州",
            "city": "成都",
            "start_date": "2025-07-10",
            "end_date": "2025-07-12",
            "interests": ["美食", "火锅"]
        },
        "expected": {
            "min_days": 3,
            "must_have_meals": True,
            "theme": "美食"
        }
    }
]
```

---

## 三、工程实践问题

### 3.1 测试完全缺失

**问题描述：**

```
没有单元测试、集成测试、端到端测试
大厂非常看重测试覆盖率
```

**解决方案：**

```python
# tests/
# ├── __init__.py
# ├── conftest.py           # pytest 配置
# ├── unit/
# │   ├── test_state.py
# │   ├── test_tools.py
# │   └── test_prompts.py
# ├── integration/
# │   ├── test_agent.py
# │   └── test_mcp.py
# └── e2e/
#     └── test_api.py

# tests/conftest.py
import pytest
import asyncio
from backend.agent import ChatSession

@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def chat_session():
    session = ChatSession()
    await session.initialize()
    yield session

# tests/unit/test_state.py
from backend.agent.state import create_initial_state, REQUIRED_FIELDS

def test_initial_state_has_required_fields():
    state = create_initial_state()
    for field in ['origin', 'city', 'start_date', 'end_date']:
        assert field in state

def test_required_fields_not_empty():
    assert len(REQUIRED_FIELDS) == 4
    assert 'city' in REQUIRED_FIELDS

# tests/integration/test_agent.py
import pytest

@pytest.mark.asyncio
async def test_chat_session_basic_flow(chat_session):
    """测试基本对话流程"""
    # 1. 获取问候
    result = await chat_session.start()
    assert result['stage'] == 'greeting'

    # 2. 发送目的地
    result = await chat_session.chat("我想去北京玩")
    assert '北京' in result['reply'] or result['collected_info'].get('city') == '北京'

    # 3. 提供日期
    result = await chat_session.chat("7月1号到7月3号")
    assert result['stage'] in ['confirming', 'collecting']

# tests/e2e/test_api.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_chat_endpoint():
    response = client.post("/api/chat", json={
        "message": "我想去北京玩三天"
    })
    assert response.status_code == 200
    assert "session_id" in response.json()
```

**运行测试：**
```bash
pytest tests/ -v --cov=backend --cov-report=html
```

---

### 3.2 错误处理粗糙

**问题描述：**

```python
# 当前代码
except Exception as e:
    print(f"[FAIL] 错误: {str(e)}")
    return {"transport_data": []}  # 静默失败
```

**解决方案：**

```python
# backend/utils/error_handler.py
from enum import Enum
from typing import Optional, Dict, Any
import functools
import asyncio

class ErrorSeverity(Enum):
    LOW = "low"           # 可忽略，不影响主流程
    MEDIUM = "medium"     # 部分功能受影响
    HIGH = "high"         # 核心功能受影响
    CRITICAL = "critical" # 系统不可用

class TravelAgentError(Exception):
    """项目基础异常"""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 user_message: Optional[str] = None, recovery_hint: Optional[str] = None):
        self.message = message
        self.severity = severity
        self.user_message = user_message or "服务暂时不可用，请稍后重试"
        self.recovery_hint = recovery_hint
        super().__init__(message)

class ToolUnavailableError(TravelAgentError):
    """工具不可用"""
    pass

class LLMTimeoutError(TravelAgentError):
    """LLM 超时"""
    pass

def with_retry(max_retries: int = 2, delay: float = 1.0,
               fallback: Optional[Dict] = None):
    """重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        await asyncio.sleep(delay * (attempt + 1))
                        print(f"[Retry] {func.__name__} 第{attempt + 1}次重试...")

            # 所有重试失败
            print(f"[Error] {func.__name__} 失败: {last_error}")
            if fallback is not None:
                return fallback
            raise last_error
        return wrapper
    return decorator

# 使用示例
@with_retry(max_retries=2, fallback={"transport_data": [], "error": "交通查询暂时不可用"})
async def query_transport(origin: str, destination: str, date: str):
    """查询交通（带重试）"""
    return await mcp_client.call_tool(...)
```

---

### 3.3 没有可观测性

**问题描述：**

```
- 没有 tracing：Agent 决策过程不可追溯
- 没有日志聚合：分散在各个 print
- 没有性能监控：响应时间、成功率
```

**解决方案：**

```python
# backend/utils/tracing.py
import time
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Span:
    """追踪单元"""
    span_id: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: list = field(default_factory=list)

    def end(self):
        self.end_time = time.time()

    @property
    def duration(self) -> float:
        return (self.end_time or time.time()) - self.start_time

class Tracer:
    """分布式追踪器"""

    def __init__(self):
        self._spans: Dict[str, Span] = {}

    def start_span(self, name: str, parent_id: Optional[str] = None) -> Span:
        span = Span(
            span_id=str(uuid.uuid4()),
            name=name,
            start_time=time.time(),
            attributes={"parent_id": parent_id} if parent_id else {}
        )
        self._spans[span.span_id] = span
        return span

    def record_event(self, span_id: str, event: str, attributes: Dict = None):
        span = self._spans.get(span_id)
        if span:
            span.events.append({
                "timestamp": datetime.now().isoformat(),
                "name": event,
                "attributes": attributes or {}
            })

# 全局追踪器
tracer = Tracer()

# 使用示例：在 Agent 节点中使用
async def attraction_node_with_tracing(state):
    span = tracer.start_span("attraction_query", parent_id=state.get("trace_id"))

    try:
        tracer.record_event(span.span_id, "llm_call_start")
        result = await llm.ainvoke(...)
        tracer.record_event(span.span_id, "llm_call_end", {"tokens": result.usage.total_tokens})

        return result
    finally:
        span.end()
        print(f"[Trace] {span.name} took {span.duration:.2f}s")
```

---

### 3.4 没有容器化部署

**问题描述：**

```
README 里是直接 uvicorn 启动
大厂项目需要：Docker、CI/CD
```

**解决方案：**

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY backend/ ./backend/

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY}
      - AMAP_MAPS_API_KEY=${AMAP_MAPS_API_KEY}
    volumes:
      - ./backend/data:/app/backend/data

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend
```

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      - name: Run tests
        run: pytest tests/ -v --cov=backend
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 四、执行计划

### Phase 1: 核心能力补全（2周）

**优先级：🔴 最高**

| 任务 | 预计时间 | 产出 |
|------|---------|------|
| 添加 RAG 知识库 | 3天 | 景点知识库 + 检索功能 |
| 用户偏好记忆 | 2天 | 向量存储用户历史 |
| 评估指标体系 | 2天 | PlanEvaluator + 测试用例 |
| 单元测试 | 3天 | 测试覆盖率 > 60% |

**验收标准：**
- [ ] 能回答"北京有什么小众景点"
- [ ] 用户第二次访问能记住偏好
- [ ] 行程质量有量化评分
- [ ] `pytest tests/` 全部通过

---

### Phase 2: Agent 智能化（2周）

**优先级：🟠 高**

| 任务 | 预计时间 | 产出 |
|------|---------|------|
| 条件路由改造 | 3天 | 动态工具选择 |
| 对话状态机 | 3天 | DialogueManager |
| 相对日期解析 | 2天 | "下周"→具体日期 |
| 工具降级机制 | 2天 | ToolRegistry |

**验收标准：**
- [ ] 用户说"不看景点"时跳过景点查询
- [ ] 用户中途修改需求能正确处理
- [ ] MCP 工具不可用时有降级方案

---

### Phase 3: 工程化完善（1周）

**优先级：🟡 中**

| 任务 | 预计时间 | 产出 |
|------|---------|------|
| 错误处理重构 | 2天 | 统一异常体系 |
| Tracing | 2天 | 决策过程可追溯 |
| Docker 化 | 1天 | Dockerfile + docker-compose |
| CI/CD | 1天 | GitHub Actions |

**验收标准：**
- [ ] 所有错误有用户友好提示
- [ ] 可通过 trace_id 查询完整决策链
- [ ] `docker-compose up` 一键启动

---

### Phase 4: 锦上添花（可选）

**优先级：🟢 低**

| 任务 | 预计时间 | 产出 |
|------|---------|------|
| 多模态支持 | 3天 | 图片识别景点 |
| 行程对比功能 | 2天 | 多方案对比 |
| 导出功能增强 | 2天 | PDF/Word/图片 |

---

## 五、面试定位建议

### 5.1 当前定位

**不要说：** "我做了一个 Agent 项目"

**要说：** "我做了一个**基于 LangGraph 的旅行规划工作流系统**，探索了 MCP 协议和专家协作模式"

这样更诚实，不会被面试官深挖 Agent 推理能力时露馅。

### 5.2 完成优化后的定位

完成 Phase 1-2 后，可以说：

> "我做了一个**基于 RAG 和 LangGraph 的智能旅行规划系统**，支持：
> - 知识库检索增强（解决小众景点推荐）
> - 用户偏好长期记忆
> - 动态工具编排（根据用户意图选择工具）
> - 完整的对话状态管理"

### 5.3 亮点提炼

面试时重点突出：

1. **技术选型的思考**
   - 为什么选 LangGraph 而不是 LangChain Agent？
   - 为什么用 MCP 而不是直接 API 调用？
   - RAG 的具体实现选择 ChromaDB/FAISS 的原因？

2. **遇到的问题和解决**
   - MCP 连接不稳定 → 实现工具降级
   - 用户模糊表达 → 相对日期解析
   - 行程质量难评估 → 设计评估指标体系

3. **数据驱动优化**
   - 通过 Tracing 发现瓶颈
   - 通过评估指标对比不同 prompt 效果

---

## 附录：技术栈对照表

| 技能点 | 当前状态 | 大厂要求 | 差距 |
|--------|---------|---------|------|
| LangChain/LangGraph | ⚠️ 基础使用 | ✅ 深度定制 | 需加强条件路由、子图 |
| RAG | ❌ 未实现 | ✅ 必须掌握 | **需尽快补齐** |
| 向量数据库 | ❌ 未使用 | ✅ 熟练使用 | 需学习 ChromaDB/Milvus |
| Function Calling | ⚠️ MCP 封装 | ✅ 原生实现 | 需补充原生调用 |
| Prompt Engineering | ⚠️ 简单模板 | ✅ 高级技巧 | 需学习 CoT、Few-shot |
| 评估体系 | ❌ 无 | ✅ 必须有 | 需设计指标 |
| 测试 | ❌ 无 | ✅ 覆盖率 > 80% | **需尽快补齐** |

---

*最后更新：2025-04-07*