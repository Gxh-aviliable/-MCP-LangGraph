# 旅游规划 Agent 项目代码审查报告

> 审查日期: 2026-03-30
> 审查范围: 后端架构、前端实现、测试覆盖、安全性

---

## 项目概述

| 项目信息 | 详情 |
|---------|------|
| 技术栈 | Python (FastAPI + LangGraph) + Vue 3 |
| 核心功能 | 多轮对话旅行规划 Agent |
| API 集成 | DeepSeek LLM + 高德地图 MCP |
| 测试覆盖 | 0% (无单元测试) |

---

## 🔴 P0 致命问题 (面试必挂级别)

### 1. ADJUSTMENT_PROMPT 模板变量从未传入 ✅ 已修复

> **修复日期**: 2026-03-30
> **修复文件**: `backend/agent/nodes/nodes.py:383-396`
> **修复内容**: 添加完整的模板变量占位符 `{current_plan}`, `{intent}`, `{target_days}`, `{action}`, `{details}`

---

**【原问题记录】**

**文件**: `backend/agent/nodes/nodes.py:376-389`

```python
# 问题代码
prompt = ChatPromptTemplate.from_messages([
    ("system", ADJUSTMENT_PROMPT),  # 包含 {current_plan}, {intent} 等变量
    ("user", "请调整行程")  # ❌ 变量根本没传入！
])

chain = prompt | llm.with_structured_output(TripPlan, method="json_mode")

response = await chain.ainvoke({
    "current_plan": plan_json,      # 这些变量传给了 chain.ainvoke
    "intent": intent,               # 但 ChatPromptTemplate 没有占位符接收它们
    "target_days": str(target_days),
    "action": action or "adjust_time",
    "details": details or "用户要求调整"
})
```

**问题分析**:
- `ADJUSTMENT_PROMPT` 定义了 `{current_plan}`, `{intent}` 等模板变量
- 但 `ChatPromptTemplate.from_messages` 只有两个固定的消息
- 传入 `ainvoke` 的字典无法匹配到任何模板变量
- LLM 收不到当前行程信息，只能凭空编造调整结果

**后果**: 多轮对话调整功能**完全失效**

**修复方案**:
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", ADJUSTMENT_PROMPT),
    ("human", """
当前行程: {current_plan}
用户意图: {intent}
目标天数: {target_days}
操作类型: {action}
详细说明: {details}
""")
])
```

---

### 2. 工具过滤逻辑存在危险 fallback ✅ 已修复

> **修复日期**: 2026-03-30
> **修复文件**: `backend/agent/nodes/nodes.py:137-158`
> **修复内容**: 移除 `tools[0]` fallback，改为抛出明确的 ValueError 异常，包含可用工具列表信息

---

**【原问题记录】**

**文件**: `backend/agent/nodes/nodes.py:143-151`

```python
# 问题代码
if "景点" in node_name or "attraction" in output_key:
    filtered_tools = [tool_name_map.get("maps_text_search", tools[0])]  # ❌
elif "天气" in node_name or "weather" in output_key:
    filtered_tools = [tool_name_map.get("maps_weather", tools[0])]  # ❌
elif "酒店" in node_name or "hotel" in output_key:
    filtered_tools = [tool_name_map.get("maps_text_search", tools[0])]  # ❌
```

**问题分析**:
- 如果 `tool_name_map` 中找不到指定工具名，fallback 到 `tools[0]`
- 景点专家可能拿着天气工具去搜索景点
- 酒店专家可能拿着错误的工具执行
- 没有任何错误提示或日志

**后果**: 工具调用失败或返回错误数据，整个规划流程崩溃

**修复方案**:
```python
if "景点" in node_name or "attraction" in output_key:
    tool = tool_name_map.get("maps_text_search")
    if not tool:
        raise ValueError(f"景点专家需要的 maps_text_search 工具未加载")
    filtered_tools = [tool]
```

---

### 3. 会话存储使用全局内存字典 ✅ 已修复

> **修复日期**: 2026-03-30
> **修复文件**: `backend/main.py:50-100`
> **修复内容**: 新增 `SessionManager` 类，支持过期清理（默认1小时），后台异步清理任务每5分钟执行，记录活跃时间

---

**【原问题记录】**

**文件**: `backend/main.py:29`

```python
# 问题代码
sessions: dict = {}  # 内存级别的会话存储
```

**问题分析**:
| 问题 | 影响 |
|------|------|
| 服务重启 | 所有用户会话丢失，用户需要重新规划 |
| 多进程部署 | 不同进程无法共享会话状态 |
| 内存泄漏 | 会话只在用户确认时删除，中途退出的会话永远残留 |
| 无过期机制 | 用户可能创建会话后几小时才回来，会话数据已过时 |

**后果**: 生产环境完全不可用

**修复方案**:
1. 短期: 添加会话过期清理机制
2. 长期: 使用 Redis 存储，设置 TTL

---

### 4. CORS 配置允许所有来源 ✅ 已修复

> **修复日期**: 2026-03-30
> **修复文件**: `backend/main.py:20-28`, `backend/config/settings.py`
> **修复内容**: 改为配置化的 `ALLOWED_ORIGINS`，默认只允许 localhost，可通过环境变量 `allowed_origins` 配置生产域名

---

**【原问题记录】**

**文件**: `backend/main.py:22`

```python
# 问题代码
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ❌ 生产环境绝对不能这样写
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**问题分析**:
- `allow_origins=["*"]` 允许任何域名的前端访问 API
- 配合 `allow_credentials=True` 存在安全风险
- 生产环境应该只允许部署的前端域名

**后果**: CSRF 攻击风险，面试官会质疑安全意识

**修复方案**:
```python
ALLOWED_ORIGINS = [
    "http://localhost:5173",  # 开发环境
    "https://your-domain.com",  # 生产环境
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    ...
)
```

---

## 🟠 P1 中等问题 (会被追问)

### 5. extract_json_from_text 正则解析过于脆弱

**文件**: `backend/agent/nodes/nodes.py:28-60`

```python
# 问题代码
json_pattern = r'(\[[\s\S]*?\]|\{[\s\S]*?\})'
matches = re.findall(json_pattern, text)
```

**问题分析**:
- LLM 输出格式不稳定，可能包含:
  - Markdown 代码块 ` ```json ... ``` `
  - 前后缀文字说明
  - 嵌套 JSON 结构
- 正则无法处理嵌套 JSON 的正确边界匹配
- `[...]` 模式会匹配到第一个 `]` 就停止，导致截断

**修复方案**:
```python
# 方案1: 使用 LLM 的 structured_output 功能，不要让 LLM 输出文本再解析
# 方案2: 使用更可靠的 JSON 解析库
from json_repair import repair_json
data = repair_json(text)
```

---

### 6. 确认关键词重复定义 ✅ 已修复

> **修复日期**: 2026-03-30
> **修复文件**: `backend/config/settings.py`, `backend/main.py`, `backend/agent/trip_agent.py`
> **修复内容**: 统一配置到 `settings.confirm_keywords`，消除重复定义，支持通过环境变量扩展

---

**【原问题记录】**

**文件**: `backend/agent/trip_agent.py:196` 和 `backend/main.py:92`

```python
# trip_agent.py
if user_input.strip() in ['确认', '满意', '好的', '可以', '没问题', 'confirm']:
    return current_plan

# main.py
if request.message.strip() in ['确认', '满意', '好的', '可以', '没问题', 'confirm']:
    del sessions[request.session_id]
```

**问题分析**:
- 同一个配置在两个地方硬编码
- 修改一处会漏掉另一处
- 无法扩展（如添加更多语言支持）

**修复方案**:
```python
# config/settings.py
CONFIRM_KEYWORDS = ['确认', '满意', '好的', '可以', '没问题', 'confirm']
```

---

### 7. 完全没有日志系统

**全项目范围**

**问题分析**:
| 缺失项 | 影响 |
|--------|------|
| 结构化日志 | 无法按级别过滤 (DEBUG/INFO/WARN/ERROR) |
| 请求追踪 | 无法追踪单个请求的完整处理链路 |
| 错误上下文 | 只有 traceback，没有业务上下文 |
| 性能监控 | 没有耗时统计，无法定位瓶颈 |

**后果**: 生产问题排查困难，面试时无法回答"如何监控和排查问题"

**修复方案**:
```python
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("travel_agent")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("logs/app.log", maxBytes=10MB, backupCount=5)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(request_id)s - %(message)s'
)
```

---

### 8. 前端错误处理过于简陋

**文件**: `frontend/src/components/TripPlanner.vue:232-234`

```typescript
// 问题代码
} catch (e: any) {
    error.value = e.message || '网络错误'  // 用户只知道"网络错误"
}
```

**问题分析**:
- 用户无法区分: 网络超时 / 服务器错误 / 业务错误
- 无法向客服提供有效的错误信息
- 没有 retry 机制

---

### 9. Settings 类缺少输入验证

**文件**: `backend/config/settings.py`

**问题分析**:
```python
class Settings(BaseSettings):
    deepseek_api_key: Optional[str] = None  # 没有格式验证
    amap_maps_api_key: Optional[str] = None  # 没有格式验证
    # 没有 start_date < end_date 的验证
    # 没有 budget_per_day >= 0 的验证
```

**后果**:
- API key 格式错误无法提前发现
- 用户输入非法日期范围会导致服务崩溃

---

## 🟡 P2 次要问题 (但有改进空间)

### 10. 测试不是单元测试

**文件**: `test/test_agent.py`

**问题分析**:
- 只有一个"运行脚本"，需要真实 API 才能执行
- 没有 mock，测试不可重复
- 没有断言，只是打印结果
- 测试覆盖率 0%

**修复方案**:
```python
# test/unit/test_nodes.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_attraction_node_with_mock_tools():
    mock_llm = MagicMock()
    mock_tool = MagicMock(name="maps_text_search")
    # ...
```

---

### 11. 类型注解大量使用 Any

**文件**: 多处

```python
def create_initial_state(request) -> Dict[str, Any]:  # 应该是 TripRequest
async def start(self, request: TripRequest) -> Optional[Dict[str, Any]]:
```

**问题分析**:
- Any 逃避了类型检查
- IDE 无法提供准确的代码补全
- 无法发挥 Pydantic 的类型安全优势

---

### 12. 前端 API 地址硬编码

**文件**: `frontend/src/api/index.ts:3`

```typescript
const API_BASE = 'http://localhost:8000/api'  // 打包后部署到哪？
```

**修复方案**:
```typescript
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'
```

---

### 13. 注释风格不统一

**全项目范围**

- 有时中文注释，有时英文注释
- 有时详细注释，有时完全没有
- 文档字符串格式不一致

---

## ✅ 项目亮点 (可以保留)

| 亮点 | 说明 |
|------|------|
| LangGraph 多 Agent 架构 | 景点→天气→酒店→规划，数据流清晰 |
| MCP 工具集成 | 展示了对新技术栈的学习能力 |
| Pydantic 数据模型 | 类型约束、验证器定义完整 |
| Vue 3 + TypeScript | 前端技术栈现代 |
| 前端 UI 完整 | 有表单、反馈、天气卡片、预算显示 |

---

## 🎯 面试高频问题预测

| 问题 | 当前答案 | 期望答案 | 备注 |
|------|----------|----------|------|
| "多轮对话调整功能测试过吗？" | ✅ 已修复 bug，待补充测试 | 有单元测试和集成测试 | 核心功能已可用 |
| "MCP 工具加载失败怎么办？" | ✅ 会抛明确异常 | 有降级策略和错误日志 | 错误信息更清晰 |
| "部署到生产环境会改什么？" | ✅ CORS/会话已改进 | Redis会话、日志系统 | 会话已支持过期清理 |
| "如何排查生产问题？" | 看print输出 | 结构化日志 + 请求追踪 | 待添加日志系统 |
| "测试覆盖率是多少？" | 0% | >80% | 待补充 pytest |

---

## 📋 修复优先级排序

| 优先级 | 问题 | 预估工时 | 影响 | 状态 |
|--------|------|----------|------|------|
| **P0** | ADJUSTMENT_PROMPT 变量未传入 | 30min | 多轮对话完全失效 | ✅ 已修复 |
| **P0** | 工具过滤 fallback 逻辑 | 20min | 工具调用可能失败 | ✅ 已修复 |
| **P0** | 会话存储改为 Redis 或定时清理 | 2h | 生产不可用 | ✅ 已修复 |
| **P0** | CORS 配置 | 10min | 安全风险 | ✅ 已修复 |
| **P1** | 添加日志系统 | 3h | 无法排查问题 | 待修复 |
| **P1** | extract_json_from_text 改进 | 1h | 解析不稳定 | 待修复 |
| **P1** | 确认关键词统一配置 | 15min | 维护困难 | ✅ 已修复 |
| **P2** | 补充 pytest 单元测试 | 4h+ | 测试覆盖率 0% | 待修复 |
| **P2** | 类型注解改进 | 2h | 类型安全 | 待修复 |
| **P2** | 前端环境变量配置 | 30min | 部署问题 | 待修复 |

---

## 总结

项目架构设计思路正确，展示了多 Agent 协作、LangGraph 状态管理、前后端分离等技术栈的理解。但**细节执行存在多处漏洞**，尤其是：

1. ~~**核心功能 bug**: 多轮对话调整代码根本不会工作~~ ✅ 已修复
2. ~~**生产级缺陷**: 会话存储、日志系统、安全配置都不达标~~ ✅ 会话存储和CORS已修复，日志系统待添加
3. **工程化缺失**: 没有真正的测试，没有持续集成意识

### 已修复问题汇总 (2026-03-30)

| 问题编号 | 问题描述 | 修复状态 |
|----------|----------|----------|
| P0-1 | ADJUSTMENT_PROMPT 模板变量未传入 | ✅ 已修复 |
| P0-2 | 工具过滤 fallback 逻辑危险 | ✅ 已修复 |
| P0-3 | 会话存储内存泄漏 | ✅ 已修复 |
| P0-4 | CORS 配置 `*` 安全风险 | ✅ 已修复 |
| P1-6 | 确认关键词重复定义 | ✅ 已修复 |

大厂面试会深挖这些细节。建议优先修复 P0 问题，再逐步完善 P1/P2。

---

> 生成工具: Claude Code
> 审查模式: 尖锐批评（面向大厂实习投递准备）