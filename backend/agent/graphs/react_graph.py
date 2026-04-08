"""ReAct Agent 图构建

构建真正的 ReAct (Reasoning + Acting) Agent 图：

结构：
┌───────────────────────────────────────────────────────────┐
│                                                           │
│  ┌──────────┐                                             │
│  │ reasoning │ ←───────────────────────────────────────┐  │
│  └─────┬────┘                                         │  │
│        ↓                                              │  │
│  ┌──────────┐                                         │  │
│  │  action  │                                         │  │
│  └─────┬────┘                                         │  │
│        ↓                                              │  │
│  ┌────────────┐                                       │  │
│  │ observation│                                       │  │
│  └─────┬──────┘                                       │  │
│        ↓                                              │  │
│  ┌────────────┐      should_continue=True             │  │
│  │ reflection │ ──────────────────────────────────────┘  │
│  └─────┬──────┘                                          │
│        │ should_continue=False                           │
│        ↓                                                 │
│       END                                                │
└───────────────────────────────────────────────────────────┘

特点：
1. 每一步都先推理 (Reasoning)
2. 根据推理结果执行行动 (Acting)
3. 观察行动结果 (Observation)
4. 反思是否需要继续 (Reflection)
5. 循环直到满意或达到最大迭代次数
"""
from typing import List
from langgraph.graph import StateGraph, END

from backend.agent.state import ChatAgentState
from backend.agent.nodes.react_nodes import (
    reasoning_node,
    action_node,
    observation_node,
    reflection_node,
)


def create_react_agent_graph(llm, tools: List):
    """创建 ReAct Agent 图

    Args:
        llm: 语言模型实例
        tools: 工具列表

    Returns:
        编译后的 StateGraph
    """
    workflow = StateGraph(ChatAgentState)

    # ==================== 添加节点 ====================

    # 核心节点
    async def reasoning(state):
        return await reasoning_node(llm, state)

    async def action(state):
        return await action_node(llm, tools, state)

    async def observation(state):
        return await observation_node(llm, state)

    async def reflection(state):
        return await reflection_node(llm, state)

    workflow.add_node("reasoning", reasoning)
    workflow.add_node("action", action)
    workflow.add_node("observation", observation)
    workflow.add_node("reflection", reflection)

    # ==================== 设置入口 ====================
    workflow.set_entry_point("reasoning")

    # ==================== 添加边 ====================

    # 线性流程
    workflow.add_edge("reasoning", "action")
    workflow.add_edge("action", "observation")
    workflow.add_edge("observation", "reflection")

    # ==================== 条件路由 ====================

    def should_continue(state: ChatAgentState) -> str:
        """决定是否继续 ReAct 循环

        返回值：
        - "continue": 继续推理
        - "end": 结束任务
        """
        # 检查是否应该继续
        should_cont = state.get('should_continue', False)
        iteration = state.get('iteration_count', 0)

        # 最大迭代次数保护
        if iteration >= 10:
            print(f"[ReAct Graph] 达到最大迭代次数 ({iteration})，结束")
            return "end"

        # 检查下一步行动
        next_action = state.get('next_action', '')
        if next_action == 'finish':
            print("[ReAct Graph] 行动为 finish，结束")
            return "end"

        # 检查质量分数
        quality_score = state.get('quality_score', 0)
        if quality_score >= 0.8:
            print(f"[ReAct Graph] 质量分数达标 ({quality_score:.2f})，结束")
            return "end"

        # 检查行程是否已生成且满意
        final_plan = state.get('final_plan')
        if final_plan and not should_cont:
            print("[ReAct Graph] 行程已生成且无需继续，结束")
            return "end"

        # 继续循环
        print(f"[ReAct Graph] 继续推理 (迭代 {iteration}, 质量 {quality_score:.2f})")
        return "continue"

    workflow.add_conditional_edges(
        "reflection",
        should_continue,
        {
            "continue": "reasoning",
            "end": END
        }
    )

    # ==================== 编译并返回 ====================
    return workflow.compile()


def create_react_planning_graph(llm, tools: List):
    """创建 ReAct 规划子图

    这是一个专门用于行程规划的子图，
    可以独立使用或嵌入到更大的对话流程中。
    """
    return create_react_agent_graph(llm, tools)


# ==================== 图可视化 ====================

def visualize_react_graph():
    """可视化 ReAct 图结构（用于调试和文档）"""
    graph_structure = """
    ReAct Agent 图结构
    ==================

    入口 → reasoning → action → observation → reflection
                                           ↓
                           ┌───────────────┘
                           ↓
                    should_continue?
                    /            \\
               True /              \\ False
                  /                \\
                 ↓                  ↓
            reasoning              END
            (循环继续)

    节点说明：
    - reasoning: 分析当前状态，决定下一步行动
    - action: 执行决定的行动（查询/生成/优化）
    - observation: 观察行动结果
    - reflection: 反思结果质量，决定是否继续

    终止条件：
    1. next_action == 'finish'
    2. quality_score >= 0.8
    3. iteration_count >= 10
    4. should_continue == False
    """
    print(graph_structure)
    return graph_structure