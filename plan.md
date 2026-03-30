# 多轮对话旅行规划系统重构方案

## 状态: ✅ 已完成

## Context

**背景**: 当前系统采用"表单 → 规划 → 反馈调整"的流程，用户体验不够自然。用户希望改为纯对话式交互：机器人主动打招呼、收集需求、分析信息完整性、确认后生成计划。

**当前流程**:
```
用户填表 → POST /api/plan → 返回行程 → 用户反馈调整
```

**目标流程**:
```
机器人打招呼 → 用户描述需求 → 分析完整性 → 缺失则追问 → 充足则确认生成 → 生成行程 → 继续对话调整
```

---

## 实现方案

### 1. 后端改造

#### 1.1 新增 API 端点 (`backend/main.py`)

新增两个 API：

```python
# POST /api/chat - 对话消息
{
  "session_id": "xxx",  # 首次可为空，后端创建新会话
  "message": "我想去北京玩几天"
}
→ 返回: {"session_id": "xxx", "reply": "...", "status": "collecting|ready|planning|done"}

# GET /api/chat/{session_id}/status - 获取会话状态
→ 返回当前需求收集状态、已有信息、缺失信息
```

#### 1.2 新增对话状态 (`backend/agent/state.py`)

在 `ChatAgentState` 中新增字段：

```python
# 需求收集状态
conversation_stage: str  # "greeting" | "collecting" | "confirming" | "planning" | "refining"
collected_info: Dict[str, Any]  # 已收集的信息
missing_fields: List[str]  # 缺失的必要字段
ready_to_plan: bool  # 是否可以开始规划
```

#### 1.3 新增对话节点 (`backend/agent/nodes/nodes.py`)

新增三个节点：

**a) greeting_node** - 初始化问候
- 输出欢迎语 + 引导用户描述需求

**b) requirement_analyzer_node** - 需求分析
- 解析用户消息，提取旅行相关信息
- 判断必要信息是否齐全（城市、日期）
- 输出缺失字段列表

**c) response_generator_node** - 响应生成
- 根据 conversation_stage 生成回复
- collecting: 提示缺失信息
- confirming: 确认是否生成计划
- refining: 处理行程调整

#### 1.4 新增提示词 (`backend/prompts/__init__.py`)

```python
REQUIREMENT_ANALYZER_PROMPT = """分析用户旅行需求，提取关键信息。

必要字段：
- city: 目的城市
- start_date: 开始日期
- end_date: 结束日期

可选字段：
- interests: 兴趣偏好
- budget: 预算
- accommodation_type: 住宿偏好

输出 JSON：
{
  "extracted": {"city": "...", "start_date": "..."},
  "missing": ["end_date"],
  "confidence": 0.8,
  "suggestions": ["请问您计划什么时候结束行程？"]
}
"""

RESPONSE_GENERATOR_PROMPT = """根据对话阶段生成回复...

阶段说明：
- greeting: 欢迎用户，介绍功能
- collecting: 提示缺失信息
- confirming: 确认是否生成计划
- planning: 正在生成
- refining: 调整行程
"""
```

#### 1.5 重构 LangGraph 流程 (`backend/agent/trip_agent.py`)

新流程图：

```
greeting → END (等待用户输入)
                    ↓
              requirement_analyzer
                    ↓
          ┌─────────┴─────────┐
          │                   │
    missing? → response → END (追问)
          │                   │
    ready? → confirming → END (等待确认)
          │                   │
    confirmed? → planning (景点/天气/酒店/规划)
                    ↓
              response → END (展示结果)
```

---

### 2. 前端改造

#### 2.1 新组件 `ChatInterface.vue`

替代 `TripPlanner.vue` 的表单部分，改为聊天界面：

```vue
<template>
  <div class="chat-container">
    <!-- 消息列表 -->
    <div class="messages">
      <div v-for="msg in messages" :class="msg.role">
        {{ msg.content }}
      </div>
    </div>

    <!-- 输入框 -->
    <div class="input-area">
      <input v-model="userInput" @keyup.enter="sendMessage" />
      <button @click="sendMessage">发送</button>
    </div>
  </div>
</template>
```

#### 2.2 状态管理

```typescript
interface ChatState {
  sessionId: string
  messages: Message[]  // 对话历史
  stage: 'greeting' | 'collecting' | 'confirming' | 'planning' | 'refining' | 'done'
  collectedInfo: object  // 已收集信息（用于展示）
  currentPlan: TripPlan | null  // 当前行程
}
```

#### 2.3 API 调用 (`frontend/src/api/index.ts`)

```typescript
// 新增对话 API
async chat(sessionId: string | null, message: string) {
  return axios.post('/api/chat', { session_id, message })
}

async getStatus(sessionId: string) {
  return axios.get(`/api/chat/${sessionId}/status`)
}
```

#### 2.4 行程展示组件复用

当 `stage === 'planning' || stage === 'refining'` 时，在聊天界面下方展示行程卡片（复用现有 TripPlanner.vue 的行程展示样式）。

---

### 3. 交互流程示例

```
[Bot]: 您好！我是旅行规划助手，可以帮您规划行程。请告诉我您想去哪里旅行？

[User]: 我想去北京

[Bot]: 北京是个好选择！请问您计划什么时候出发？行程大概几天？

[User]: 下周出发，玩3天

[Bot]: 我理解您想去北京，下周出发玩3天。请问具体是哪一天出发？另外有什么特别想看的景点或兴趣偏好吗？

[User]: 4月5号出发，喜欢历史古迹

[Bot]: 好的，我已了解您的需求：
- 目的地：北京
- 日期：4月5日 - 4月7日（3天）
- 兴趣：历史古迹

是否现在为您生成旅行计划？（输入"是"或"生成"开始规划）

[User]: 是

[Bot]: 正在为您规划北京行程...请稍候...

[Bot]: 行程已生成！[展示行程卡片]

您对这个行程满意吗？有需要调整的地方可以直接告诉我。
```

---

## 关键文件修改清单

| 文件 | 改动 |
|------|------|
| `backend/main.py` | 新增 `/api/chat` 端点，重构 SessionManager |
| `backend/agent/state.py` | 新增 `conversation_stage`, `collected_info`, `missing_fields` 字段 |
| `backend/agent/trip_agent.py` | 重构 LangGraph 流程图 |
| `backend/agent/nodes/nodes.py` | 新增 `greeting_node`, `requirement_analyzer_node`, `response_generator_node` |
| `backend/prompts/__init__.py` | 新增 `REQUIREMENT_ANALYZER_PROMPT`, `RESPONSE_GENERATOR_PROMPT` |
| `backend/model/schemas.py` | 新增 `ChatRequest`, `ChatResponse` 模型 |
| `frontend/src/api/index.ts` | 新增 `chat()` API |
| `frontend/src/components/ChatInterface.vue` | 新增聊天界面组件 |
| `frontend/src/components/TripPlanner.vue` | 重构为聊天+行程展示组合 |
| `frontend/src/App.vue` | 引入新组件 |

---

## 验证方式

1. **启动服务**: `npm run dev` + `uvicorn backend.main:app --reload`
2. **打开前端**: http://localhost:5173
3. **验证流程**:
   - 页面加载后自动显示机器人问候语
   - 输入"我想去北京玩" → 机器人追问日期
   - 输入"下周玩3天" → 机器人追问具体日期
   - 输入"4月5号" → 机器人确认需求
   - 输入"生成" → 显示行程
   - 输入"第一天景点太多" → 调整行程

---

## 设计决定（已确认）

1. **日期解析**: 两者结合 - 支持 LLM 解析相对日期，但优先追问确认具体日期
2. **行程展示**: 聊天流中显示 - 行程作为一条消息卡片出现在对话中
3. **会话持久化**: 需要 - 前端将 sessionId 保存到 localStorage，支持刷新后继续

---

## 待确认问题

~~1. **日期解析**: 用户说"下周"、"明天"如何转换为具体日期？是否需要额外处理？~~
~~2. **会话持久化**: 是否需要前端保存 sessionId 到 localStorage，支持刷新后继续？~~
~~3. **行程展示位置**: 行程卡片是在聊天流中显示，还是固定在页面下方？~~