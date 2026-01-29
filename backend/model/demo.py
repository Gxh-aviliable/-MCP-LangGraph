from fastapi import FastAPI, HTTPException
from typing import List, Optional
# 假设你之前的模型都在 models.py 中
from schemas import TripPlanResponse, TripPlan, DayPlan, WeatherInfo, Budget 

app = FastAPI(title="AI 多智能体旅行助手 API")

@app.post("/generate-plan", response_model=TripPlanResponse)
async def generate_travel_plan(destination: str, days: int):
    """
    模拟多智能体系统生成旅行计划的接口
    """
    try:
        # 1. 这里通常是调用你的 Multi-Agent 系统 (如 LangChain 或 CrewAI)
        # agent_output = await travel_agents_group.run(destination, days)
        
        # 2. 模拟生成的数据（实际开发中这里由 AI 生成并解析为模型对象）
        mock_plan = TripPlan(
            city=destination,
            start_date="2024-05-01",
            end_date="2024-05-03",
            days=[], # 填充 DayPlan 对象列表
            weather_info=[], 
            overall_suggestions="建议携带雨伞，穿轻便的运动鞋。",
            budget=None
        )

        # 3. 返回符合 TripPlanResponse 结构的数据
        return TripPlanResponse(
            success=True,
            message="行程规划生成成功",
            data=mock_plan
        )

    except Exception as e:
        # 如果中间环节出错，返回 success=False
        return TripPlanResponse(
            success=False,
            message=f"生成失败: {str(e)}",
            data=None
        )

if __name__ == "__main__":
    print("--- 准备进入 Uvicorn ---") # 新增这一行
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)