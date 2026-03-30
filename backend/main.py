"""FastAPI 后端服务

启动方式:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agent import TripChatSession
from backend.model import TripRequest, FeedbackRequest

# 创建 FastAPI 应用
app = FastAPI(
    title="Travel Planning Agent API",
    description="多轮对话旅行规划 Agent",
    version="1.0.0"
)

# CORS 配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 会话存储（简单实现，生产环境应使用 Redis 等）
sessions: dict = {}


# ===================== API 路由 =====================

@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "message": "Travel Planning Agent API"}


@app.post("/api/plan")
async def create_plan(request: TripRequest):
    """创建旅行规划

    返回 session_id 用于后续多轮对话
    """
    print(f"\n[API] 收到规划请求: {request.city}, {request.start_date} - {request.end_date}")

    try:
        # 创建会话
        session = TripChatSession()
        await session.initialize()

        # 执行规划
        plan = await session.start(request)

        if not plan:
            return {"success": False, "error": "规划失败"}

        # 保存会话
        session_id = session.thread_id
        sessions[session_id] = session

        print(f"[API] 规划完成, session_id: {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "plan": plan
        }

    except Exception as e:
        print(f"[API ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    """提交反馈，继续多轮对话"""
    print(f"\n[API] 收到反馈: session={request.session_id}, message={request.message}")

    session = sessions.get(request.session_id)

    if not session:
        return {"success": False, "error": "会话不存在或已过期"}

    try:
        plan = await session.feedback(request.message)

        # 如果用户确认满意，清理会话
        if request.message.strip() in ['确认', '满意', '好的', '可以', '没问题', 'confirm']:
            del sessions[request.session_id]
            print(f"[API] 会话结束: {request.session_id}")

        return {
            "success": True,
            "plan": plan
        }

    except Exception as e:
        print(f"[API ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.get("/api/plan/{session_id}")
async def get_plan(session_id: str):
    """获取当前行程"""
    session = sessions.get(session_id)

    if not session:
        return {"success": False, "error": "会话不存在"}

    plan = await session.get_current_plan()
    return {"success": True, "plan": plan}


# ===================== 启动入口 =====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)