# 快速启动指南

## 环境要求

- Python 3.10+
- Node.js 18+

## 1. 配置环境变量

复制 `.env.example` 为 `.env` 并填写 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写以下配置：
- `DEEPSEEK_API_KEY` - DeepSeek API 密钥
- `AMAP_MAPS_API_KEY` - 高德地图 API 密钥

## 2. 启动后端

```bash
# 创建虚拟环境（可选）
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r backend/requirements.txt

# 启动服务
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

后端运行在 http://localhost:8000

## 3. 启动前端

新开一个终端窗口：

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端运行在 http://localhost:5173

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| POST | `/api/plan` | 创建旅行规划 |
| POST | `/api/feedback` | 提交反馈 |
| GET | `/api/plan/{session_id}` | 获取当前行程 |