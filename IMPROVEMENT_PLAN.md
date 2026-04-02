# intern_project 暑期实习全面改进计划

> 基于 travel-planning-agent 项目的优秀设计，对 intern_project 进行全面升级

---

## 一、背景与目标

### 1.1 当前项目现状

| 维度 | 现状 | 问题 |
|------|------|------|
| 架构 | FastAPI + LangGraph + Vue3 | 架构良好 |
| 模型 | 单一 DeepSeek 模型 | 无法根据场景复杂度选择模型 |
| 工具 | 仅高德地图 POI + 天气 | 缺少火车票、黄历、航班等 |
| 知识库 | 无 | 无 RAG 向量检索 |

### 1.2 改进目标

1. **功能完整性**: 添加12306、黄历、航班、RAG知识库等工具
2. **智能化升级**: 引入双模型协作(Qwen3 + DeepSeek R1)
3. **工程质量**: 完善测试、日志、错误处理
4. **用户体验**: 优化前端展示效果

---

## 二、改进模块概览

| 模块 | 优先级 | 预计工作量 | 核心改动 |
|------|--------|-----------|---------|
| 模块1: 双模型协作 | P0 | 2天 | 引入Qwen3，实现智能分流 |
| 模块2: 工具扩展 | P0 | 3天 | 添加12306、黄历、航班、自驾路线 |
| 模块3: RAG知识库 | P1 | 2天 | ChromaDB向量检索 |
| 模块4: MCP重试机制 | P1 | 0.5天 | 工具调用容错 |
| 模块5: 前端优化 | P2 | 1天 | 交通对比展示、行程详情 |
| 模块6: 测试与文档 | P2 | 1天 | 单元测试、API文档 |

**总计: 约9-10个工作日**

---

## 三、详细改进方案

### 模块1: 双模型协作架构 (P0) [预计2天]

#### 1.1 新增配置

**文件**: `backend/config/settings.py`

```python
class Settings(BaseSettings):
    # 现有配置...
    deepseek_api_key: Optional[str] = None

    # 新增配置
    dashscope_api_key: Optional[str] = None  # 阿里云Qwen3

    # 模型选择
    primary_model: str = "qwen-plus"  # 主模型(日常决策)
    reasoning_model: str = "deepseek-reasoner"  # 推理模型(复杂场景)
```

#### 1.2 新增智能分流模块

**新文件**: `backend/agent/router.py`

```python
async def analyze_query_complexity(user_query: str, llm) -> dict:
    """分析查询复杂度，决定使用哪个模型"""
    # 检测多目的地
    # 检测预算紧张
    # 检测特殊需求(老人/儿童)
    # 返回: { "scenario_type": "simple|complex|multi_destination", "needs_r1": bool }
```

#### 1.3 修改 Agent 入口

**文件**: `backend/agent/trip_agent.py`

- [ ] 添加 Qwen3 LLM 实例
- [ ] 在 `ChatAgentSystem` 中添加模型选择逻辑
- [ ] 复杂场景调用 R1 进行深度分析

#### 1.4 新增 R1 分析工具

**新文件**: `backend/agent/tools/r1_tool.py`

```python
class DeepSeekR1Analyzer:
    """DeepSeek R1 深度分析器"""
    async def analyze(self, problem: str, context: dict) -> str:
        # 调用 deepseek-reasoner 模型
        # 用于: 多目的地路线优化、预算优化、复杂约束分析
```

---

### 模块2: 工具扩展 (P0) [预计3天]

#### 2.1 工具注册表

**新文件**: `backend/agent/tools/tool_registry.py`

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    tool_type: str  # "mcp" | "r1" | "rag"
    server_name: Optional[str]  # MCP服务器名
    mcp_tool_name: Optional[str]  # MCP工具名

AVAILABLE_TOOLS = [
    # 12306火车票
    ToolDefinition(
        name="train_query",
        description="查询12306火车票信息",
        tool_type="mcp",
        server_name="12306 Server",
        mcp_tool_name="get-tickets"
    ),
    # 黄历查询
    ToolDefinition(
        name="lucky_day",
        description="查询黄历吉日",
        tool_type="mcp",
        server_name="bazi Server",
        mcp_tool_name="getChineseCalendar"
    ),
    # 航班查询
    ToolDefinition(
        name="flight_query",
        description="查询航班信息(距离>800km时使用)",
        tool_type="mcp",
        server_name="flight Server",
        mcp_tool_name="searchFlightsByDepArr"
    ),
    # 自驾路线
    ToolDefinition(
        name="gaode_driving",
        description="查询自驾路线(距离、时间、过路费)",
        tool_type="mcp",
        server_name="Gaode Server",
        mcp_tool_name="maps_direction_driving"
    ),
    # ... 现有工具
]
```

#### 2.2 MCP 配置扩展

**新文件**: `backend/config/mcp_config.json`

```json
{
    "mcp_servers": [
        {"name": "12306 Server", "url": "${MCP_12306_URL}"},
        {"name": "Gaode Server", "url": "${MCP_GAODE_URL}"},
        {"name": "bazi Server", "url": "${MCP_BAZI_URL}"},
        {"name": "flight Server", "url": "${MCP_FLIGHT_URL}"}
    ]
}
```

#### 2.3 火车票查询工具实现

**文件**: `backend/agent/tools/mcp_tools.py` (修改)

```python
async def query_train_tickets(origin: str, destination: str, date: str) -> dict:
    """查询火车票(含站点代码转换)"""
    # 1. 获取站点代码
    from_codes = await get_station_codes(origin)
    to_codes = await get_station_codes(destination)

    # 2. 查询车票
    tickets = await mcp_call("12306 Server", "get-tickets", ...)

    # 3. 同时查询自驾路线(用于对比)
    driving = await query_driving_route(origin, destination)

    return {"train": tickets, "driving": driving}
```

---

### 模块3: RAG知识库 (P1) [预计2天]

#### 3.1 新增 RAG 模块

**新文件**: `backend/agent/tools/rag_tool.py`

```python
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings

class TravelRAGTool:
    """旅游攻略向量检索工具"""

    def __init__(self):
        self.embeddings = DashScopeEmbeddings(
            model="text-embedding-v3",
            dashscope_api_key=settings.dashscope_api_key
        )
        self.vectorstore = Chroma(
            persist_directory="./data/travel_vectordb",
            embedding_function=self.embeddings
        )

    def search(self, query: str, k: int = 5) -> list:
        """检索相关旅游攻略"""
        return self.vectorstore.similarity_search(query, k=k)

    def build_knowledge_base(self, data_dir: str):
        """从文档构建知识库"""
        # 支持 TXT, PDF, CSV, MD
```

#### 3.2 数据目录结构

```
backend/
├── data/
│   ├── travel_docs/          # 旅游攻略文档
│   │   └── sample_guides.txt
│   └── travel_vectordb/      # ChromaDB 向量数据库
```

#### 3.3 集成到 Agent

**文件**: `backend/agent/nodes/nodes.py`

在景点搜索节点中，先调用 RAG 检索知识库，再调用高德 POI 搜索。

---

### 模块4: MCP重试机制 (P1) [预计0.5天]

**文件**: `backend/agent/tools/mcp_tools.py` (修改)

```python
class MCPToolManager:
    async def call_tool(self, server_name, tool_name, max_retries=2, **kwargs):
        """带重试的MCP工具调用"""
        for attempt in range(max_retries + 1):
            try:
                result = await self.mcp_servers[server_name].call_tool(...)
                return self._parse_result(result)
            except Exception as e:
                if self._is_retryable(e) and attempt < max_retries:
                    await asyncio.sleep(1 * attempt)  # 指数退避
                    continue
                raise

    def _is_retryable(self, error) -> bool:
        """判断错误是否可重试"""
        retryable_errors = [
            "peer closed connection",
            "incomplete chunked read",
            "timeout",
            "connection reset"
        ]
        return any(e in str(error).lower() for e in retryable_errors)
```

---

### 模块5: 前端优化 (P2) [预计1天]

#### 5.1 交通方案对比组件

**新文件**: `frontend/src/components/TransportComparison.vue`

```vue
<template>
  <div class="transport-comparison">
    <div class="transport-option" v-for="option in options" :key="option.type">
      <div class="transport-icon">{{ option.icon }}</div>
      <div class="transport-details">
        <div class="transport-name">{{ option.name }}</div>
        <div class="transport-info">
          <span>⏱️ {{ option.duration }}</span>
          <span>💰 ¥{{ option.cost }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
```

#### 5.2 行程详情优化

**文件**: `frontend/src/components/PlanCard.vue` (修改)

- [ ] 添加天气信息展示
- [ ] 添加黄历信息展示
- [ ] 添加交通方案对比
- [ ] 添加每日详细行程折叠面板

#### 5.3 数据模型扩展

**文件**: `backend/model/schemas.py` (修改)

```python
class TransportOption(BaseModel):
    """交通方案"""
    type: str  # "train" | "driving" | "flight"
    name: str
    duration: str
    cost: int
    details: dict

class LuckyDayInfo(BaseModel):
    """黄历信息"""
    date: str
    lunar_date: str
    suitable: List[str]  # 宜
    avoid: List[str]     # 忌

class TripPlan(BaseModel):
    # 现有字段...
    transport_options: List[TransportOption] = []  # 新增
    lucky_day_info: Optional[LuckyDayInfo] = None  # 新增
```

---

### 模块6: 测试与文档 (P2) [预计1天]

#### 6.1 单元测试

**新文件**: `backend/tests/test_tools.py`

```python
@pytest.mark.asyncio
async def test_train_query():
    """测试火车票查询"""
    result = await query_train_tickets("上海", "北京", "2026-04-15")
    assert "train" in result
    assert "driving" in result

async def test_rag_search():
    """测试RAG检索"""
    rag = TravelRAGTool()
    results = rag.search("苏州景点")
    assert len(results) > 0
```

#### 6.2 API 文档

FastAPI 自动生成 Swagger 文档，访问 `/docs` 即可。

#### 6.3 README 更新

更新项目说明，包括：
- 新增功能列表
- 环境变量配置说明
- 启动步骤

---

## 四、环境变量配置

**文件**: `.env.example` (更新)

```env
# === 模型 API ===
DEEPSEEK_API_KEY=sk-xxx          # DeepSeek API (R1推理模型)
DASHSCOPE_API_KEY=sk-xxx         # 阿里云DashScope (Qwen3 + Embedding)

# === 高德地图 ===
AMAP_MAPS_API_KEY=xxx            # 高德地图 API Key

# === MCP 服务器 (可选，使用ModelScope公共服务) ===
MCP_12306_URL=https://xxx/sse    # 12306 MCP服务
MCP_GAODE_URL=https://xxx/sse    # 高德地图 MCP服务
MCP_BAZI_URL=https://xxx/sse     # 黄历 MCP服务
MCP_FLIGHT_URL=https://xxx/sse   # 航班 MCP服务

# === 应用配置 ===
DEBUG=false
SESSION_EXPIRE_SECONDS=3600
```

---

## 五、依赖更新

**文件**: `requirements.txt` (新增)

```txt
# 现有依赖...

# 新增依赖
langchain-chroma>=0.1.0          # ChromaDB向量存储
dashscope>=1.14.0                # 阿里云Qwen3 SDK
```

---

## 六、验证方案

### 6.1 功能验证

```bash
# 1. 启动后端
cd backend
uvicorn main:app --reload

# 2. 启动前端
cd frontend
npm run dev

# 3. 测试场景
# - 简单查询: "苏州有什么好玩的？"
# - 完整规划: "我想从上海去苏州玩2天，预算1500元，明天出发"
# - 多目的地: "我想从上海去苏州和杭州玩4天"
# - 复杂场景: "带2个老人和1个儿童，预算紧张"
```

### 6.2 接口验证

```bash
# 健康检查
curl http://localhost:8000/

# 对话接口
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "我想去北京玩3天"}'

# 查看API文档
open http://localhost:8000/docs
```

---

## 七、风险与注意事项

1. **API Key 获取**: 需要提前申请 DashScope API Key (阿里云)
2. **MCP 服务器**: 可以使用 ModelScope 公共服务或自建
3. **向后兼容**: 新功能保持与现有API兼容，不影响前端
4. **渐进式改进**: 可以按模块逐步实施，每个模块独立可测试

---

## 八、实施顺序建议

```
Week 1:
  Day 1-2: 模块1 (双模型协作)
  Day 3-5: 模块2 (工具扩展 - 12306/黄历/航班)

Week 2:
  Day 1-2: 模块3 (RAG知识库)
  Day 3: 模块4 (MCP重试机制) + 模块5 (前端优化)
  Day 4-5: 模块6 (测试与文档) + 整体联调
```

---

## 九、执行检查清单

### 模块1: 双模型协作
- [ ] 更新 `backend/config/settings.py` 添加 DashScope 配置
- [ ] 创建 `backend/agent/router.py` 智能分流模块
- [ ] 创建 `backend/agent/tools/r1_tool.py` R1分析工具
- [ ] 修改 `backend/agent/trip_agent.py` 集成双模型

### 模块2: 工具扩展
- [ ] 创建 `backend/agent/tools/tool_registry.py` 工具注册表
- [ ] 创建 `backend/config/mcp_config.json` MCP配置
- [ ] 修改 `backend/agent/tools/mcp_tools.py` 添加新工具
- [ ] 更新 `.env.example` 添加新的环境变量

### 模块3: RAG知识库
- [ ] 创建 `backend/agent/tools/rag_tool.py` RAG工具
- [ ] 创建 `backend/data/` 目录结构
- [ ] 修改 `backend/agent/nodes/nodes.py` 集成RAG

### 模块4: MCP重试机制
- [ ] 修改 `backend/agent/tools/mcp_tools.py` 添加重试逻辑

### 模块5: 前端优化
- [ ] 创建 `frontend/src/components/TransportComparison.vue`
- [ ] 修改 `frontend/src/components/PlanCard.vue`
- [ ] 修改 `backend/model/schemas.py` 添加新模型

### 模块6: 测试与文档
- [ ] 创建 `backend/tests/` 目录和测试文件
- [ ] 更新 `README.md`
- [ ] 更新 `requirements.txt`

---

## 十、参考资源

- **travel-planning-agent**: `D:/intern_work/travel-planning-agent-main`
- **DashScope API**: https://dashscope.aliyun.com/
- **DeepSeek API**: https://platform.deepseek.com/
- **ModelScope MCP**: https://www.modelscope.cn/