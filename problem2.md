# 后端测试问题汇总

测试日期: 2026-03-25

---

## 测试环境

- 平台: Windows 10
- Python: 3.10
- 模型: DeepSeek Chat
- MCP: amap-mcp-server

---

## 测试结果概览

| 模块 | 状态 | 说明 |
|------|------|------|
| 配置加载 | ✅ 通过 | API Keys 正确读取 |
| Schema 定义 | ⚠️ 部分问题 | 温度解析有Bug |
| MCP 工具加载 | ✅ 通过 | 成功加载16个工具 |
| MCP 酒店搜索 | ✅ 支持 | maps_text_search 可搜索酒店 |
| Agent 工具调用 | ⚠️ 部分问题 | 可调用但效率低 |
| LLM 结构化输出 | ✅ 通过 | json_mode 正常工作 |

---

## 发现的问题

### 问题 1: 温度解析器 Bug (高优先级)

**文件**: `backend/model/schemas.py:73-82`

**现象**: 当温度格式为 `"16C"` (没有度数符号) 时，解析返回 `0` 而不是 `16`

**原因**: `field_validator` 只处理了以下格式:
- `°C`
- `℃`
- `°`

但未处理单独的 `C` 或 `c`

**测试结果**:
```
Input '16':   PASS (结果: 16)
Input '16C':  FAIL (结果: 0, 期望: 16)
Input '16°C': PASS (结果: 16)
Input '16℃': PASS (结果: 16)
```

**修复建议**:
```python
@field_validator('day_temp','night_temp',mode='before')
def parse_temperature(cls,v):
    if isinstance(v,str):
        v = v.replace('°C','').replace('℃','').replace('°','').replace('C','').replace('c','').strip()
        try:
            return int(v)
        except ValueError:
            return 0
    return v
```

---

### 问题 2: PLANNER_AGENT_PROMPT 与 Schema 不匹配 (高优先级)

**文件**: `backend/agent/trip_agent.py:75-107`

**现象**: LLM 按照提示词输出 JSON，但无法通过 Schema 验证

**原因**: 提示词中使用占位符 `{...}` 和 `[...]`，未指定完整的字段结构

**不匹配的字段**:

| Schema 字段 | 要求 | Prompt 是否说明 |
|-------------|------|-----------------|
| `attractions.address` | 必填 | ❌ 未说明 |
| `attractions.location` | 必填 | ❌ 未说明 |
| `attractions.visit_duration` | 必填 | ❌ 未说明 |
| `attractions.ticket_price` | int 类型 | ❌ 未说明（LLM可能输出 "60元"） |
| `weather_info.day_weather` | 必填 | ⚠️ 可能使用 "weather" |
| `weather_info.night_weather` | 必填 | ❌ 未说明 |
| `weather_info.day_temp` | 必填，int | ❌ 未说明 |
| `weather_info.wind_direction` | 必填 | ❌ 未说明 |
| `weather_info.wind_power` | 必填 | ❌ 未说明 |
| `meals.type` | 必填 | ❌ 未说明 |
| `meals.name` | 必填 | ❌ 未说明 |

**修复建议**: 在 `PLANNER_AGENT_PROMPT` 中提供完整的 JSON 示例，包含所有必填字段

---

### 问题 3: Agent 执行效率低 (中优先级)

**文件**: `backend/agent/trip_agent.py`

**现象**: Agent 处理时间过长，测试超时

**原因**:
1. LLM 进行多次工具调用（搜索多个关键词）
2. 每次工具调用都是串行的
3. 部分搜索失败后重试（SSL 错误）

**测试输出**:
```
Invoking: maps_text_search with {'keywords': '历史古迹', 'city': '北京'}
Invoking: maps_text_search with {'keywords': '古建筑', 'city': '北京'}  # SSL Error
Invoking: maps_text_search with {'keywords': '遗址', 'city': '北京'}
Invoking: maps_text_search with {'keywords': '王府', 'city': '北京'}
Invoking: maps_text_search with {'keywords': '恭王府', 'city': '北京'}
Invoking: maps_text_search with {'keywords': '钟鼓楼', 'city': '北京'}
...
```

**修复建议**:
1. 限制 Agent 的最大迭代次数
2. 优化 Prompt，要求一次返回结果
3. 添加超时控制

---

### 问题 4: 数据提取逻辑不完整 (低优先级)

**文件**: `backend/agent/trip_agent.py:271-291`

**现象**: Agent 从 MCP 工具输出提取数据时，可能遗漏部分数据

**当前逻辑**:
```python
list_keys = ['hotels', 'pois', 'attractions', 'weather', 'forecasts']
for k in list_keys:
    if k in raw_json and isinstance(raw_json[k], list):
        structured_data.extend(raw_json[k])
        found_list = True
        break
```

**问题**: `break` 导致只提取第一个匹配的列表，可能遗漏其他数据

---

### 问题 5: 缺少 `__init__.py` 文件 (低优先级)

**现象**: `backend/` 目录下缺少 `__init__.py` 文件

**影响**: 可能导致某些导入场景失败

**修复建议**:
- 添加 `backend/__init__.py`
- 添加 `backend/model/__init__.py`
- 添加 `backend/agent/__init__.py`
- 添加 `backend/config/__init__.py`

---

### 问题 6: 错误处理不完善 (低优先级)

**文件**: `backend/agent/trip_agent.py`

**现象**:
1. API 调用失败时（如 SSL 错误），Agent 继续尝试但没有明确提示
2. 缺少重试机制和错误恢复

---

## 测试通过的项

### ✅ 模块导入
- `schemas.py` 正确导入
- `settings.py` 正确导入
- 配置从 `.env` 正确加载

### ✅ MCP 工具加载
```
Loaded 16 tools:
- maps_regeocode
- maps_geo
- maps_ip_location
- maps_weather
- maps_bicycling_by_address
- maps_direction_walking_by_address
- maps_direction_driving_by_address
- maps_direction_transit_integrated_by_address
- maps_distance
- maps_text_search
- maps_around_search
- maps_search_detail
- etc.
```

### ✅ LLM 结构化输出
- `with_structured_output(TripPlan, method="json_mode")` 正常工作
- 可以生成符合 Schema 的空行程

### ✅ Agent 工具调用
- `maps_text_search` 工具被正确调用
- 返回真实的景点数据（颐和园、故宫、天坛等）

---

## 修复优先级

1. **高优先级** (影响核心功能)
   - 问题 1: 温度解析器 Bug
   - 问题 2: Prompt 与 Schema 不匹配

2. **中优先级** (影响性能)
   - 问题 3: Agent 执行效率低

3. **低优先级** (代码质量)
   - 问题 4: 数据提取逻辑
   - 问题 5: 缺少 `__init__.py`
   - 问题 6: 错误处理不完善

---

## 补充: 高德地图 MCP 服务能力确认

### 酒店搜索能力 ✅ 支持

经测试，高德地图 MCP 服务**完全支持酒店查询**：

**测试结果**:
```
使用 maps_text_search 搜索关键词 "酒店" + 城市 "北京":
- 北京艺栈青年酒店(燕莎亮马桥地铁站店) @ 新源南路甲3号佳亿广场F4层
- 北京宝格丽酒店 @ 新源南路8号院2号楼
- 北京漫朵乐享酒店 @ 马家楼路1号院东区4号楼2层
```

**可用的酒店搜索工具**:

| 工具 | 功能 | 适用场景 |
|------|------|----------|
| `maps_text_search` | 关键词搜索 | 按城市搜索酒店 |
| `maps_around_search` | 周边搜索 | 按景点/位置周边搜索酒店 |
| `maps_search_detail` | POI详情 | 获取酒店详细信息(价格、评分等) |

**之前"酒店返回0数据"的原因**:

不是 MCP 服务的问题，而是 **Agent 行为问题**：
1. `HOTEL_AGENT_PROMPT` 可能引导不够明确
2. DeepSeek 模型可能未正确触发工具调用
3. Agent 返回了文本回答而非调用工具

**建议**: 优化 `HOTEL_AGENT_PROMPT`，强制要求必须调用工具

---

## 建议的修复步骤

1. **第一步**: 修复温度解析器
   - 修改 `schemas.py` 中的 `parse_temperature` 方法

2. **第二步**: 完善 PLANNER_AGENT_PROMPT
   - 提供完整的 JSON 示例，包含所有必填字段
   - 明确字段类型要求

3. **第三步**: 优化 Agent 性能
   - 添加迭代次数限制
   - 添加超时控制

4. **第四步**: 添加缺失的 `__init__.py` 文件

5. **第五步**: 改进错误处理