"""FastAPI 后端服务

启动方式:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

架构设计：
    - 共享资源层（MCP工具、LLM）：启动时初始化一次，所有会话共用
    - 状态层（LangGraph）：每个会话独立，保证对话隔离
"""
import time
import asyncio
import json
from typing import Dict, Optional, Union, AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from backend.agent import ChatSession, TripChatSession, SharedResourceManager
from backend.model import TripRequest, FeedbackRequest, ChatRequest, ChatResponse
from backend.config.settings import settings

# ===================== 配置 =====================

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
    - 支持两种会话类型：ChatSession（对话式）和 TripChatSession（表单式）
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

    def set(self, session_id: str, session: Union[ChatSession, TripChatSession]):
        """存储会话"""
        self._sessions[session_id] = {
            'session': session,
            'last_active': time.time()
        }

    def get(self, session_id: str) -> Optional[Union[ChatSession, TripChatSession]]:
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
    description="对话式旅行规划 Agent",
    version="2.0.0"
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
    """应用启动时初始化共享资源

    架构说明：
    - SharedResourceManager 是全局单例，管理 MCP 工具和 LLM
    - 启动时初始化一次，后续所有会话共用（毫秒级创建）
    - 每个会话有独立的 LangGraph 和 Checkpointer（状态隔离）
    """
    await session_manager.start_cleanup_task()
    print(f"[Startup] CORS 允许的来源: {ALLOWED_ORIGINS}")
    print(f"[Startup] 会话过期时间: {session_manager._expire_seconds} 秒")

    # 初始化共享资源（MCP 工具、LLM）
    print("[Startup] 初始化共享资源（MCP 工具、LLM）...")
    try:
        manager = await asyncio.wait_for(
            SharedResourceManager.ensure_initialized(),
            timeout=120.0  # 给足够的初始化时间（MCP 需要 60+ 秒）
        )
        tools = manager.get_tools()
        print("[Startup] 共享资源初始化成功!")
        print(f"[Startup] 已加载 {len(tools)} 个 MCP 工具，所有会话将共用")
        print("[Startup] 新会话创建将只需毫秒级（无需重新初始化 MCP）")

    except asyncio.TimeoutError:
        print("[Startup] 共享资源初始化超时（120秒）")
        print("[Startup] 请检查 MCP 服务是否正常")
    except Exception as e:
        print(f"[Startup] 共享资源初始化失败: {e}")


# ===================== API 路由 =====================

@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "message": "Travel Planning Agent API v2.0"}


# ===================== 对话式 API =====================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话式交互 API

    - 首次调用可不传 session_id，系统会创建新会话并返回问候消息
    - 后续调用需传入 session_id 以保持对话上下文
    - 返回的 stage 表示当前对话阶段：
      - greeting: 问候阶段
      - collecting: 收集信息阶段
      - confirming: 确认阶段
      - planning: 规划中
      - refining: 调整阶段
      - done: 完成
    """
    try:
        # 获取或创建会话
        if request.session_id:
            session = session_manager.get(request.session_id)
            if not session:
                return ChatResponse(
                    success=False,
                    session_id=request.session_id,
                    reply="会话不存在或已过期，请刷新页面重新开始。",
                    stage="done",
                    collected_info=None,
                    missing_fields=[],
                    plan=None
                )
        else:
            # 创建新的对话会话（使用共享资源，毫秒级）
            session = ChatSession()
            # 传递用户选择的 Agent 模式
            agent_mode = getattr(request, 'agent_mode', 'smart') or 'smart'
            await session.initialize(agent_mode=agent_mode)
            session_manager.set(session.thread_id, session)
            print(f"[API] 新建会话: {session.thread_id[:8]}... (模式: {agent_mode})")

        # 如果是首次对话，返回问候
        if not request.session_id and not request.message:
            result = await session.start()
            return ChatResponse(
                success=True,
                session_id=session.thread_id,
                reply=result['reply'],
                stage=result['stage'],
                collected_info=result['collected_info'],
                missing_fields=result['missing_fields'],
                plan=None
            )

        # 处理用户消息
        result = await session.chat(request.message)

        # 检查是否需要清理会话
        if result['stage'] == 'done':
            session_manager.delete(session.thread_id)
            print(f"[API] 会话结束: {session.thread_id}")

        return ChatResponse(
            success=True,
            session_id=session.thread_id,
            reply=result['reply'],
            stage=result['stage'],
            collected_info=result.get('collected_info'),
            missing_fields=result.get('missing_fields', []),
            plan=result.get('plan')
        )

    except Exception as e:
        print(f"[API ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return ChatResponse(
            success=False,
            session_id=request.session_id or "",
            reply=f"抱歉，发生了错误：{str(e)}",
            stage="collecting",
            collected_info=None,
            missing_fields=[],
            plan=None
        )


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话 API - 使用 SSE 实时推送进度

    返回 SSE 事件流，包含：
    - event: message / stage / plan / error / done
    - data: JSON 格式的数据
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            # 获取或创建会话
            if request.session_id:
                session = session_manager.get(request.session_id)
                if not session:
                    yield _sse_event("error", {"message": "会话不存在或已过期"})
                    return
            else:
                session = ChatSession()
                agent_mode = getattr(request, 'agent_mode', 'smart') or 'smart'
                await session.initialize(agent_mode=agent_mode)
                session_manager.set(session.thread_id, session)
                print(f"[Stream] 新建会话: {session.thread_id[:8]}... (模式: {agent_mode})")

            # 发送会话ID
            yield _sse_event("session", {"session_id": session.thread_id})

            # 如果是首次对话，返回问候
            if not request.session_id and not request.message:
                result = await session.start()
                yield _sse_event("message", {"content": result['reply']})
                yield _sse_event("stage", {"stage": result['stage']})
                yield _sse_event("done", {})
                return

            # 发送进度消息
            yield _sse_event("message", {"content": "正在思考中..."})

            # 处理用户消息
            result = await session.chat(request.message)

            # 发送回复
            yield _sse_event("message", {"content": result['reply']})

            # 发送阶段
            yield _sse_event("stage", {
                "stage": result['stage'],
                "collected_info": result.get('collected_info'),
                "missing_fields": result.get('missing_fields', [])
            })

            # 如果有行程，发送行程数据
            if result.get('plan'):
                yield _sse_event("plan", {"plan": result['plan']})

            # 完成信号
            yield _sse_event("done", {})

            # 清理会话
            if result['stage'] == 'done':
                session_manager.delete(session.thread_id)

        except Exception as e:
            print(f"[Stream ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            yield _sse_event("error", {"message": f"发生错误：{str(e)}"})

    return EventSourceResponse(generate())


def _sse_event(event: str, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/chat/{session_id}/status")
async def get_chat_status(session_id: str):
    """获取会话状态"""
    session = session_manager.get(session_id)

    if not session:
        return {"success": False, "error": "会话不存在或已过期"}

    state = await session.get_current_state()

    return {
        "success": True,
        "session_id": session_id,
        "stage": state.get('conversation_stage', 'greeting'),
        "collected_info": state.get('collected_info', {}),
        "missing_fields": state.get('missing_fields', []),
        "has_plan": state.get('final_plan') is not None
    }


# ===================== 兼容旧版 API =====================

@app.post("/api/plan")
async def create_plan(request: TripRequest):
    """创建旅行规划（兼容旧版表单模式）

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
    """提交反馈，继续多轮对话（兼容旧版）"""
    print(f"\n[API] 收到反馈: session={request.session_id}, message={request.message}")

    session = session_manager.get(request.session_id)

    if not session:
        return {"success": False, "error": "会话不存在或已过期"}

    try:
        plan = await session.feedback(request.message)

        # 如果用户确认满意，清理会话
        if request.message.strip() in settings.confirm_keywords:
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