# 🚀 快速启动指南

## 概述

这是一个 **AI 智能旅行规划助手**，基于多智能体架构实现。
- 🎯 **后端**: FastAPI + LangGraph + 多智能体
- 🎨 **前端**: Vue3 + Element Plus
- 💬 **通信**: HTTP API + WebSocket

## 系统要求

- Python 3.10+
- Node.js 16+
- npm 或 yarn

## 最快启动（3 种方式）

### 方式 1️⃣: Windows 批处理脚本（推荐）

```cmd
双击运行 start.bat

然后选择:
1. 安装依赖
2. 启动后端
3. 在新终端启动前端
```

### 方式 2️⃣: Linux/Mac Shell 脚本

```bash
chmod +x start.sh
./start.sh

然后选择菜单选项
```

### 方式 3️⃣: Docker Compose（推荐用于生产）

```bash
# 安装 Docker Desktop 后运行
docker-compose up

# 访问:
# 前端: http://localhost
# 后端 API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

---

## 手动启动步骤

### 第 1 步: 安装依赖

**后端**:
```bash
cd backend
pip install -r requirements.txt
cd ..
```

**前端**:
```bash
cd frontend
npm install
cd ..
```

### 第 2 步: 启动后端

```bash
cd backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

✅ 后端将在 http://localhost:8000 启动

📖 API 文档: http://localhost:8000/docs (交互式文档)

### 第 3 步: 启动前端（新终端）

```bash
cd frontend
npm run dev
```

✅ 前端将在 http://localhost:5173 启动

---

## 功能演示

### 1. 打开前端

访问 http://localhost:5173

### 2. 填写表单

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

### 3. 点击"🚀 开始规划"

系统将自动:
- 🎯 搜索景点信息
- 🌤️ 查询天气预报
- 🏨 推荐酒店
- 📅 生成详细行程

---

## API 文档

### 快速参考

| 方法 | 端点 | 说明 |
|-----|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/cities` | 获取热门城市 |
| GET | `/api/interests` | 获取兴趣分类 |
| GET | `/api/accommodation-types` | 获取住宿类型 |
| POST | `/api/plan` | 生成旅行计划（同步） |
| WS | `/ws/plan` | 实时规划（WebSocket） |

### 示例请求

```bash
# 使用 curl 测试 API
curl -X GET http://localhost:8000/health

curl -X GET http://localhost:8000/api/cities

curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "city": "北京",
    "start_date": "2026-01-30",
    "end_date": "2026-02-02",
    "interests": ["故宫"],
    "accommodation_type": "五星级",
    "budget_per_day": 1500,
    "transportation_mode": "地铁+出租车"
  }'
```

### 使用 Python 测试

```bash
python test_api.py
```

---

## 项目结构

```
trip-planner/
├── backend/
│   ├── api/
│   │   └── main.py              # FastAPI 主应用
│   ├── agent/
│   │   ├── demo_trip_agent.py   # 多智能体系统
│   │   └── demo.py
│   ├── model/
│   │   └── schemas.py           # 数据模型
│   ├── requirements.txt         # Python 依赖
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── TripForm.vue     # 旅行表单
│   │   │   └── TripResult.vue   # 结果展示
│   │   ├── stores/
│   │   │   └── tripStore.js     # 状态管理
│   │   ├── utils/
│   │   │   └── api.js           # API 客户端
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
│
├── docker-compose.yml
├── start.bat                     # Windows 启动脚本
├── start.sh                      # Linux/Mac 启动脚本
├── test_api.py                   # API 测试
└── README.md                     # 完整文档
```

---

## 常见问题

### Q: 后端启动时报错 "❌ MCP 初始化失败"

**A**: 检查 API Key 是否正确配置
```python
# backend/api/main.py 中修改
DEEPSEEK_KEY = "your-key"
AMAP_KEY = "your-key"
```

### Q: 前端无法连接到后端

**A**: 检查代理配置
```javascript
// 如果在开发环境遇到 CORS 问题，
// vite.config.js 已配置代理，
// 确保后端运行在 8000 端口
```

### Q: WebSocket 连接失败

**A**: 使用 HTTP 备选方案（前端已自动处理）
- 确保后端支持 WebSocket
- 某些防火墙可能阻止 WebSocket

### Q: 生成计划很慢

**A**: 这是正常的（首次需要 30-60 秒）
- 系统需要：调用外部 API、LLM 推理、数据处理
- 后续相同查询会更快（如果实现了缓存）

### Q: 如何修改 API Key？

**A**: 三种方式：

1. **硬编码**（仅用于开发）
```python
# backend/api/main.py
DEEPSEEK_KEY = "sk-xxx"
AMAP_KEY = "xxx"
```

2. **环境变量**
```bash
export DEEPSEEK_API_KEY=sk-xxx
export AMAP_MAPS_API_KEY=xxx
```

3. **Docker Compose**
```yaml
environment:
  - DEEPSEEK_API_KEY=sk-xxx
  - AMAP_MAPS_API_KEY=xxx
```

---

## 性能优化建议

### 1. 后端优化
- 添加 Redis 缓存
- 使用连接池
- 并行执行智能体

### 2. 前端优化
- 构建时进行代码分割
- 使用懒加载
- 压缩资源文件

### 3. 数据库
- 存储规划历史
- 收集分析数据

---

## 部署到生产环境

### 使用 Heroku

```bash
heroku create your-app-name
heroku config:set DEEPSEEK_API_KEY=sk-xxx
heroku config:set AMAP_MAPS_API_KEY=xxx
git push heroku main
```

### 使用云服务器

```bash
# AWS EC2, 阿里云, 腾讯云 等

# 1. 安装依赖
pip install -r backend/requirements.txt
npm install --prefix frontend

# 2. 构建前端
npm run build --prefix frontend

# 3. 使用 Gunicorn + Nginx
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.api.main:app
```

---

## 获取帮助

### 查看完整文档
```bash
cat README.md
```

### API 交互式文档
访问: http://localhost:8000/docs

### 查看后端日志
```bash
# Docker 方式
docker-compose logs -f backend

# 本地方式
# 终端中直接查看输出
```

### 查看前端控制台
打开浏览器 → F12 → Console

---

## 下一步

1. ✅ 启动应用
2. ✅ 尝试生成行程计划
3. ✅ 导出为 JSON
4. ✅ 查看 API 文档
5. ✅ 自定义功能或部署

---

## 联系与支持

有问题或建议？
- 📧 发送邮件
- 💬 提交 Issue
- 🤝 提交 PR

**祝您使用愉快！🎉**

---

**文档更新于**: 2026-01-30  
**版本**: 1.0.0
