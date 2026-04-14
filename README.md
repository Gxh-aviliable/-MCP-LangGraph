# Travel Planning Agent

基于 LangGraph 和 MCP 的对话式旅行规划智能体系统。

## 项目简介

这是一个智能旅行规划助手，用户可以通过自然对话描述旅行需求，系统会自动收集信息、查询景点/天气/酒店/交通，并生成详细的行程计划。支持行程调整和多轮对话交互。

### 核心特性

- **对话式交互**：用户无需填写表单，通过自然对话即可完成需求描述
- **ReAct Agent 架构**：支持动态推理和决策，根据查询结果调整后续行动
- **MCP 工具集成**：集成高德地图、12306 等外部工具，获取实时数据
- **流式输出**：使用 SSE 实时推送生成进度，提升用户体验
- **行程评估**：自动评估生成行程的质量，支持迭代优化
- **PDF 导出**：支持将行程导出为 PDF 文件

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Vue 3)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ ChatInterface│  │  PlanCard   │  │    TripPlanner     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          └────────────────┼────────────────────┘
                           │ HTTP/SSE
┌──────────────────────────┼──────────────────────────────────┐
│                     Backend (FastAPI)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   Session Manager                      │   │
│  │         (会话管理 + 过期清理 + 状态持久化)               │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Shared Resource Manager                   │   │
│  │          (MCP 工具池 + LLM 实例共享)                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   LangGraph Agent                      │   │
│  │  ┌─────────────┐    ┌─────────────┐                   │   │
│  │  │  Chat Graph │    │  Plan Graph │                   │   │
│  │  │ (对话流程)   │    │ (规划流程)   │                   │   │
│  │  └─────────────┘    └─────────────┘                   │   │
│  │                                                        │   │
│  │  ┌─────────────────────────────────────────────────┐  │   │
│  │  │              ReAct Agent Loop                    │  │   │
│  │  │  reasoning → action → observation → reflection  │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    MCP Tools (外部服务)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ 高德地图 API  │  │  12306 API   │  │   其他 MCP 服务   │   │
│  │ (景点/天气/   │  │  (火车票查询) │  │  (可扩展接入)     │   │
│  │  酒店/导航)   │  │              │  │                  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## 技术栈

### 后端
- **框架**: FastAPI + Uvicorn
- **Agent 框架**: LangGraph + LangChain
- **工具协议**: MCP (Model Context Protocol)
- **LLM**: 阿里云通义千问 (Qwen) via DashScope API
- **状态管理**: LangGraph MemorySaver

### 前端
- **框架**: Vue 3 + TypeScript
- **构建工具**: Vite
- **HTTP 客户端**: Axios
- **PDF 导出**: html2pdf.js

## 目录结构

```
.
├── backend/
│   ├── agent/                 # Agent 核心逻辑
│   │   ├── graphs/           # LangGraph 图定义
│   │   │   └── react_graph.py    # ReAct Agent 图
│   │   ├── nodes/            # Agent 节点
│   │   │   ├── nodes.py          # 业务节点（景点/天气/酒店查询）
│   │   │   └── react_nodes.py    # ReAct 推理节点
│   │   ├── state.py          # 状态定义
│   │   ├── router.py         # 意图路由
│   │   └── trip_agent.py     # 会话管理
│   ├── config/               # 配置管理
│   │   ├── settings.py       # 应用配置
│   │   └── mcp_config.json   # MCP 服务配置
│   ├── evaluation/           # 行程评估
│   │   └── evaluator.py      # 质量评估器
│   ├── model/                # 数据模型
│   │   └── schemas.py        # Pydantic 模型
│   ├── prompts/              # 提示词模板
│   ├── tests/                # 测试文件
│   │   ├── unit/             # 单元测试
│   │   └── integration/      # 集成测试
│   ├── utils/                # 工具函数
│   └── main.py               # FastAPI 入口
├── frontend/
│   ├── src/
│   │   ├── components/       # Vue 组件
│   │   │   ├── ChatInterface.vue  # 对话界面
│   │   │   ├── PlanCard.vue       # 行程卡片
│   │   │   └── TripPlanner.vue    # 表单模式
│   │   ├── api/              # API 封装
│   │   └── main.ts           # 入口文件
│   └── package.json
└── requirements.txt
```

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- uvx (用于运行 MCP 工具)

### 1. 克隆项目

```bash
git clone <repository-url>
cd intern_project
```

### 2. 后端配置

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r backend/requirements.txt

# 配置环境变量
cp .env.example .env
```

编辑 `.env` 文件，填入必要的 API Key：

```env
# 阿里云 DashScope API Key (通义千问)
DASHSCOPE_API_KEY=your_dashscope_api_key

# 高德地图 API Key
AMAP_MAPS_API_KEY=your_amap_api_key
```

### 3. 前端配置

```bash
cd frontend
npm install
```

### 4. 启动服务

**启动后端**：
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**启动前端**：
```bash
cd frontend
npm run dev
```

访问 http://localhost:5173 即可使用。

## API 文档

启动后端后，访问以下地址查看 API 文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 主要接口

| 接口 | 方法 | 说明 |
|-----|------|------|
| `/api/chat` | POST | 对话式交互（同步） |
| `/api/chat/stream` | POST | 对话式交互（流式 SSE） |
| `/api/chat/{session_id}/status` | GET | 获取会话状态 |
| `/api/plan` | POST | 表单模式创建行程 |
| `/api/feedback` | POST | 提交行程反馈 |

### 对话流程阶段

| 阶段 | 说明 |
|-----|------|
| `greeting` | 问候阶段，展示欢迎信息 |
| `collecting` | 信息收集阶段，收集必要参数 |
| `optional_collecting` | 可选参数引导 |
| `confirming` | 确认阶段，询问是否生成行程 |
| `planning` | 规划中，生成行程 |
| `refining` | 调整阶段，根据反馈修改行程 |
| `done` | 完成 |

## Agent 模式

系统支持两种 Agent 模式：

### 1. 智能模式 (Smart)
- 高效流水线模式
- 预定义流程，快速生成行程
- 适合简单、明确的需求

### 2. ReAct 模式
- 动态推理模式
- 根据 Agent 思考链动态决策
- 支持多轮迭代优化
- 适合复杂、需要调整的需求

```
ReAct 循环:
┌──────────┐     ┌──────────┐     ┌────────────┐     ┌────────────┐
│ Reasoning │ ──▶ │  Action  │ ──▶ │ Observation │ ──▶ │ Reflection │
└──────────┘     └──────────┘     └────────────┘     └─────┬──────┘
                                                              │
                    ┌────────────────────────────────────────┘
                    ▼
            should_continue?
            /            \
       True /              \ False
          /                \
         ▼                  ▼
    Reasoning              END
    (继续循环)
```

## 测试

```bash
# 运行所有测试
pytest backend/tests/

# 运行单元测试
pytest backend/tests/unit/

# 带覆盖率报告
pytest --cov=backend backend/tests/
```

## 配置说明

### MCP 服务配置

编辑 `backend/config/mcp_config.json` 配置额外的 MCP 服务：

```json
{
  "mcp_servers": [
    {
      "name": "amap",
      "enabled": true,
      "transport": "stdio",
      "command": "uvx",
      "args": ["amap-mcp-server"]
    }
  ]
}
```

### 应用配置

通过环境变量或 `.env` 文件配置：

| 变量 | 说明 | 默认值 |
|-----|------|-------|
| `DASHSCOPE_API_KEY` | 阿里云 API Key | 必填 |
| `AMAP_MAPS_API_KEY` | 高德地图 API Key | 必填 |
| `PRIMARY_MODEL` | 使用的模型 | `qwen-plus` |
| `LLM_TEMPERATURE` | 模型温度 | `0.7` |
| `SESSION_EXPIRE_SECONDS` | 会话过期时间 | `3600` |
| `DEBUG` | 调试模式 | `false` |

## 项目亮点

1. **真正的 Agent 架构**：基于 LangGraph 构建，支持状态管理和流程控制
2. **ReAct 推理循环**：Agent 可以根据结果动态调整策略，而非固定流水线
3. **MCP 工具协议**：采用 Anthropic 推动的标准工具协议，易于扩展
4. **共享资源管理**：MCP 工具全局共享，新会话创建毫秒级
5. **流式交互体验**：SSE 实时推送，用户可以看到生成进度
6. **行程质量评估**：自动评估完整性、时间合理性、预算准确性等维度

## 待优化项

- [ ] 路线优化算法：基于实际距离计算最优游览顺序
- [ ] 更多测试覆盖：核心 Agent 逻辑的单元测试
- [ ] 缓存机制：减少重复 API 调用
- [ ] 多语言支持
- [ ] 历史行程管理

## License

MIT License