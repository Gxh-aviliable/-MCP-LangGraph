"""
FastAPI 后端 - 旅行推荐服务
支持 WebSocket 实时进度反馈和普通 HTTP 请求
"""
import asyncio
import json
import logging
from typing import Optional
from datetime import datetime
from pathlib import Path
import sys

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.schemas import TripRequest, TripPlanResponse, TripPlan
from agent.trip_agent import TripGraphSystem

# ===================== 日志配置 =====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== FastAPI 应用 =====================
app = FastAPI(
    title="旅行推荐系统",
    description="基于多智能体的旅行规划助手",
    version="1.0.0"
)

# ===================== CORS 配置 =====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== 全局状态 =====================
# 存储活跃的 WebSocket 连接和任务
active_connections: dict[str, WebSocket] = {}
active_tasks: dict[str, asyncio.Task] = {}
system_instance: Optional[TripGraphSystem] = None

# ===================== 启动/关闭事件 =====================
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化系统"""
    global system_instance
    logger.info("🚀 正在初始化旅行推荐系统...")
    
    # 从环境变量或配置读取 API Key（生产环境应使用环境变量）
    DEEPSEEK_KEY = "sk-5c6052d783934e59a0a3a73066a3cdcd"
    AMAP_KEY = "0ed6e5ef8effdc096432cd039075c0fc"
    
    try:
        system_instance = TripGraphSystem(DEEPSEEK_KEY, AMAP_KEY)
        await system_instance.initialize()
        logger.info("✅ 系统初始化成功")
    except Exception as e:
        logger.error(f"❌ 系统初始化失败: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    logger.info("🛑 正在关闭应用...")
    
    # 关闭所有 WebSocket 连接
    for connection_id, ws in active_connections.items():
        try:
            await ws.close()
        except Exception as e:
            logger.warning(f"关闭连接 {connection_id} 时出错: {str(e)}")
    
    # 取消所有活跃任务
    for task_id, task in active_tasks.items():
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

# ===================== 健康检查 =====================
@app.get("/health", tags=["健康检查"])
async def health_check():
    """检查服务是否在线"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "trip-planner"
    }

# ===================== HTTP 接口 =====================
@app.post("/api/plan", response_model=TripPlanResponse, tags=["旅行规划"])
async def plan_trip(request: TripRequest):
    """
    生成旅行计划（同步接口）
    
    Args:
        request: 旅行请求信息
    
    Returns:
        TripPlanResponse: 包含旅行计划的响应
    """
    if not system_instance:
        raise HTTPException(
            status_code=503,
            detail="系统未初始化，请稍后重试"
        )
    
    try:
        logger.info(f"📋 收到旅行规划请求: {request.city} {request.start_date}~{request.end_date}")
        
        # 构建图
        app_graph = system_instance.create_graph()
        
        # 准备输入
        inputs = {
            "city": request.city,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "interests": request.interests,
            "accommodation_type": request.accommodation_type,
            "budget_per_day": request.budget_per_day,
            "transportation_mode": request.transportation_mode,
            "attractions_data": [],
            "weather_data": [],
            "hotels_data": [],
            "context": [],
            "execution_errors": [],
            "final_plan": None,
        }
        
        # 执行规划
        final_state = await app_graph.ainvoke(inputs)
        
        # 提取结果
        final_plan = final_state.get("final_plan")
        execution_errors = final_state.get("execution_errors", [])
        
        if execution_errors:
            logger.warning(f"⚠️ 执行过程中出现错误: {execution_errors}")
        
        if final_plan:
            logger.info("✅ 行程规划成功")
            return TripPlanResponse(
                success=True,
                message="行程规划成功",
                data=final_plan
            )
        else:
            logger.error("❌ 未能生成行程计划")
            return TripPlanResponse(
                success=False,
                message="未能生成行程计划，请检查输入参数",
                data=None
            )
    
    except ValidationError as e:
        logger.error(f"❌ 输入验证失败: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"输入数据格式错误: {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"❌ 规划过程出错: {str(e)}")
        return TripPlanResponse(
            success=False,
            message=f"规划过程出错: {str(e)}",
            data=None
        )

# ===================== WebSocket 接口（实时进度反馈） =====================
@app.websocket("/ws/plan")
async def websocket_plan_trip(websocket: WebSocket):
    """
    WebSocket 接口 - 实时接收旅行规划请求并返回进度
    
    消息格式:
    {
        "action": "plan",
        "data": {
            "city": "北京",
            "start_date": "2026-01-30",
            "end_date": "2026-02-02",
            "interests": ["故宫", "国家博物馆"],
            "accommodation_type": "五星级",
            "budget_per_day": 1500,
            "transportation_mode": "地铁+出租车"
        }
    }
    """
    if not system_instance:
        await websocket.close(code=1011, reason="系统未初始化")
        return
    
    connection_id = f"ws_{id(websocket)}"
    await websocket.accept()
    active_connections[connection_id] = websocket
    
    logger.info(f"✅ WebSocket 连接已建立: {connection_id}")
    
    try:
        while True:
            # 接收客户端消息
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "JSON 格式错误"
                })
                continue
            
            # 处理规划请求
            if message.get("action") == "plan":
                try:
                    # 验证请求数据
                    request = TripRequest(**message.get("data", {}))
                    
                    # 发送开始消息
                    await websocket.send_json({
                        "type": "start",
                        "message": f"开始规划 {request.city} 的旅行计划...",
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 构建图
                    app_graph = system_instance.create_graph()
                    
                    # 准备输入
                    inputs = {
                        "city": request.city,
                        "start_date": request.start_date,
                        "end_date": request.end_date,
                        "interests": request.interests,
                        "accommodation_type": request.accommodation_type,
                        "budget_per_day": request.budget_per_day,
                        "transportation_mode": request.transportation_mode,
                        "attractions_data": [],
                        "weather_data": [],
                        "hotels_data": [],
                        "context": [],
                        "execution_errors": [],
                        "final_plan": None,
                    }
                    
                    # 执行规划（可以添加进度回调）
                    final_state = await app_graph.ainvoke(inputs)
                    
                    # 发送进度消息
                    for context_msg in final_state.get("context", []):
                        await websocket.send_json({
                            "type": "progress",
                            "message": context_msg,
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # 提取结果
                    final_plan = final_state.get("final_plan")
                    execution_errors = final_state.get("execution_errors", [])
                    
                    # 发送错误消息（如果有）
                    for error in execution_errors:
                        await websocket.send_json({
                            "type": "warning",
                            "message": error,
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # 发送最终结果
                    if final_plan:
                        await websocket.send_json({
                            "type": "success",
                            "message": "行程规划完成",
                            "data": final_plan,
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "未能生成行程计划",
                            "timestamp": datetime.now().isoformat()
                        })
                
                except ValidationError as e:
                    logger.error(f"❌ 输入验证失败: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"输入数据格式错误: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
                
                except Exception as e:
                    logger.error(f"❌ 规划过程出错: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"规划过程出错: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
            
            # 处理心跳包
            elif message.get("action") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"未知的操作: {message.get('action')}"
                })
    
    except Exception as e:
        logger.error(f"❌ WebSocket 错误: {str(e)}")
    
    finally:
        # 清理连接
        if connection_id in active_connections:
            del active_connections[connection_id]
        
        # 取消相关任务
        if connection_id in active_tasks:
            task = active_tasks[connection_id]
            if not task.done():
                task.cancel()
            del active_tasks[connection_id]
        
        logger.info(f"❌ WebSocket 连接已关闭: {connection_id}")

# ===================== 静态信息接口 =====================
@app.get("/api/cities", tags=["参考数据"])
async def get_popular_cities():
    """获取热门城市列表"""
    cities = [
        {"name": "北京", "description": "中国首都，历史文化名城"},
        {"name": "上海", "description": "国际大都市，金融中心"},
        {"name": "杭州", "description": "西湖之城，电商中心"},
        {"name": "西安", "description": "古都，丝绸之路起点"},
        {"name": "成都", "description": "休闲城市，美食天堂"},
        {"name": "南京", "description": "六朝古都，历史底蕴深厚"},
        {"name": "苏州", "description": "园林城市，水乡风情"},
        {"name": "广州", "description": "羊城，经济贸易中心"},
    ]
    return {
        "success": True,
        "data": cities
    }

@app.get("/api/interests", tags=["参考数据"])
async def get_interest_categories():
    """获取兴趣分类"""
    interests = [
        {"category": "历史文化", "items": ["故宫", "长城", "兵马俑", "大雁塔"]},
        {"category": "自然风景", "items": ["西湖", "黄山", "张家界", "九寨沟"]},
        {"category": "现代建筑", "items": ["东方明珠", "环球金融中心", "鸟巢"]},
        {"category": "美食体验", "items": ["北京烤鸭", "麻辣火锅", "小笼包"]},
        {"category": "购物娱乐", "items": ["南京路", "王府井", "春熙路"]},
        {"category": "宗教信仰", "items": ["寺庙", "佛寺", "道观", "教堂"]},
        {"category": "城市公园", "items": ["公园", "植物园", "动物园"]},
    ]
    return {
        "success": True,
        "data": interests
    }

@app.get("/api/accommodation-types", tags=["参考数据"])
async def get_accommodation_types():
    """获取住宿类型"""
    types = [
        {"name": "五星级", "description": "高端豪华酒店"},
        {"name": "四星级", "description": "中高档酒店"},
        {"name": "三星级", "description": "中档酒店"},
        {"name": "经济型", "description": "经济型酒店"},
        {"name": "民宿", "description": "民居客栈"},
        {"name": "青年旅舍", "description": "背包客旅舍"},
    ]
    return {
        "success": True,
        "data": types
    }

# ===================== 文档 =====================
if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 启动旅行推荐系统服务...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
