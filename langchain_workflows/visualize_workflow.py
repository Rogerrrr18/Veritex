# -*- coding: utf-8 -*-
# 文件名：visualize_agent_workflow.py
# 用途：生成 Veritex Agent 工作流结构图（Graphviz）
#
# 依赖安装：
#   brew install graphviz   # macOS
#   pip install graphviz

from graphviz import Digraph

dot = Digraph("VeritexAgent", format="svg")
dot.attr(rankdir="LR", labelloc="t", fontsize="14", label="Veritex Agent 工作流（LangGraph 状态机）")

# 核心节点
dot.node("START", "START", shape="circle", style="filled", fillcolor="#e2f0ff")
dot.node("intent", "Intent Analysis\n(intent_analysis)", shape="box", style="rounded,filled", fillcolor="#ffffff")
dot.node("chat", "Chat Conversation\n(chat_conversation)", shape="box", style="rounded,filled", fillcolor="#ffffff")
dot.node("lit", "Literature Search\n(literature_search)\n仅分析+关键词扩展（缓存）", shape="box", style="rounded,filled", fillcolor="#ffffff")
dot.node("exec", "Search Execution\n(search_execution)\n多源并行检索", shape="box", style="rounded,filled", fillcolor="#ffffff")
dot.node("fmt", "Result Formatting\n(result_formatting)", shape="box", style="rounded,filled", fillcolor="#ffffff")
dot.node("disc", "Academic Discussion\n(academic_discussion)", shape="box", style="rounded,filled", fillcolor="#ffffff")
dot.node("END", "END", shape="doublecircle", style="filled", fillcolor="#e2f0ff")

# 主干边
dot.edge("START", "intent")

dot.edge("intent", "chat", label="intent=闲聊", fontsize="11")
dot.edge("intent", "lit", label="intent=查文献", fontsize="11")
dot.edge("intent", "disc", label="intent=学术探讨", fontsize="11")

dot.edge("chat", "END", label="对话完成", fontsize="11")

# literature_search 分支
dot.edge("lit", "exec", label="mode=auto-search 且 should_search=True", fontsize="11", color="#0ea5e9")
dot.edge("lit", "END", label="mode=chat&plan → 等待用户确认", fontsize="11", style="dashed", color="#64748b")
dot.edge("lit", "END", label="mode=auto-search 但缺少标记 → 结束/等待", fontsize="11", style="dashed", color="#64748b")

# 搜索执行与结果
dot.edge("exec", "fmt")
dot.edge("fmt", "END")

# 学术探讨
dot.edge("disc", "END", label="默认结束（可建议搜索）", fontsize="11")
# 可选：若未来开启自动建议直达检索，启用虚线
dot.edge("disc", "exec", label="(可选) search_suggestion=True", fontsize="11", style="dotted", color="#94a3b8")

# 说明节点（图例）
with dot.subgraph(name="cluster_legend") as c:
    c.attr(label="图例", fontsize="12", color="#94a3b8")
    c.node("legend1", "圆角方框：处理节点\n圆圈：开始/结束\n蓝色边：auto-search 自动触发检索\n灰色虚线：等待用户确认/可选路径", shape="note", style="filled", fillcolor="#f8fafc")

# 输出
outpath = dot.render(filename="agent_workflow")
print(f"✅ 生成完成：{outpath}")