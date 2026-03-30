"""FastAPI 后端服务

启动方式:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""
import time
import asyncio
from typing import Dict, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agent import TripChatSession
from backend.model import TripRequest, FeedbackRequest
from backend.config.settings import settings

# ===================== 配置 =====================

# 确认关键词（从统一配置读取）
CONFIRM_KEYWORDS = settings.confirm_keywords

# CORS 允许的来源（从配置读取，支持环境变量覆盖）
ALLOWED_ORIGINS = settings.allowed_origins
if not ALLOWED_ORIGINS:
    # 默认配置：开发环境允许 localhost，生产环境应通过环境变量配置
    ALLOWED_ORIGINS = [
        "http://localhost:5173",   # Vite 开发服务器
        "http://localhost:3000",   # 其他常见前端端口
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

# ===================== 会话存储（带过期清理） =====================

class SessionManager:
    """会话管理器 - 支持过期清理

    解决问题:
    - 内存泄漏：会话不再永久残留
    - 过期机制：长时间不活跃的会话会被清理
    """

    def __init__(self, expire_seconds: int = 3600):
        """
        Args:
            expire_seconds: 会话过期时间（秒），默认 1 小时
        """
        self._sessions: Dict[str, Dict] = {}
        self._expire_seconds = expire_seconds
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self):
        """启动后台清理任务"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            print("[SessionManager] 后台清理任务已启动")

    async def _cleanup_loop(self):
        """定期清理过期会话"""
        while True:
            try:
                await asyncio.sleep(300)  # 每 5 分钟检查一次
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[SessionManager] 清理任务异常: {e}")

    def _cleanup_expired(self):
        """清理过期会话"""
        current_time = time.time()
        expired_keys = []

        for session_id, session_data in self._sessions.items():
            last_active = session_data.get('last_active', 0)
            if current_time - last_active > self._expire_seconds:
                expired_keys.append(session_id)

        for session_id in expired_keys:
            del self._sessions[session_id]
            print(f"[SessionManager] 清理过期会话: {session_id}")

        if expired_keys:
            print(f"[SessionManager] 本次清理 {len(expired_keys)} 个过期会话")

    def set(self, session_id: str, session: TripChatSession):
        """存储会话"""
        self._sessions[session_id] = {
            'session': session,
            'last_active': time.time()
        }

    def get(self, session_id: str) -> Optional[TripChatSession]:
        """获取会话（同时更新活跃时间）"""
        session_data = self._sessions.get(session_id)
        if session_data:
            session_data['last_active'] = time.time()
            return session_data['session']
        return None

    def delete(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return session_id in self._sessions

    def count(self) -> int:
        """当前活跃会话数量"""
        return len(self._sessions)


# 全局会话管理器实例
session_manager = SessionManager(expire_seconds=settings.session_expire_seconds)


# ===================== FastAPI 应用 =====================

app = FastAPI(
    title="Travel Planning Agent API",
    description="多轮对话旅行规划 Agent",
    version="1.0.0"
)

# CORS 配置（安全配置，不再使用 *）
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    await session_manager.start_cleanup_task()
    print(f"[Startup] CORS 允许的来源: {ALLOWED_ORIGINS}")
    print(f"[Startup] 会话过期时间: {session_manager._expire_seconds} 秒")


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

        # 保存会话（使用新的会话管理器）
        session_id = session.thread_id
        session_manager.set(session_id, session)

        print(f"[API] 规划完成, session_id: {session_id}, 当前活跃会话: {session_manager.count()}")

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

    session = session_manager.get(request.session_id)

    if not session:
        return {"success": False, "error": "会话不存在或已过期"}

    try:
        plan = await session.feedback(request.message)

        # 如果用户确认满意，清理会话（使用统一配置的确认关键词）
        if request.message.strip() in CONFIRM_KEYWORDS:
            session_manager.delete(request.session_id)
            print(f"[API] 会话结束: {request.session_id}, 剩余会话: {session_manager.count()}")

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
    session = session_manager.get(session_id)

    if not session:
        return {"success": False, "error": "会话不存在或已过期"}

    plan = await session.get_current_plan()
    return {"success": True, "plan": plan}


# ===================== 启动入口 =====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)