# -*- coding: utf-8 -*-
# 文件名：visualize_agent_workflow.py
# 用途：生成 Veritex Agent 工作流结构图（Graphviz）
#
# 依赖安装：
#   brew install graphviz   # macOS
#   pip install graphviz

try:
    from graphviz import Digraph
    GRAPHVIZ_AVAILABLE = True
except Exception:
    GRAPHVIZ_AVAILABLE = False


def build_dot_source() -> str:
    lines = []
    lines.append("digraph VeritexAgent {")
    lines.append("  rankdir=LR; labelloc=t; fontsize=14; label=\"Veritex Agent 工作流（LangGraph 状态机）\";")
    # 节点样式
    lines.append('  START [label="START", shape=circle, style="filled", fillcolor="#e2f0ff"];')
    lines.append('  router [label="模式路由\\n(route_by_mode)\\n+ 快速闲聊过滤", shape=box, style="rounded,filled", fillcolor="#ffffff"];')
    lines.append('  chat [label="Chat Conversation\\n(chat_conversation)", shape=box, style="rounded,filled", fillcolor="#ffffff"];')
    lines.append('  lit [label="Literature Search\\n(literature_search)\\n仅分析 + 关键词扩展（缓存）", shape=box, style="rounded,filled", fillcolor="#ffffff"];')
    lines.append('  exec [label="Search Execution\\n(search_execution)\\n多源并行检索", shape=box, style="rounded,filled", fillcolor="#ffffff"];')
    lines.append('  fmt [label="Result Formatting\\n(result_formatting)", shape=box, style="rounded,filled", fillcolor="#ffffff"];')
    lines.append('  disc [label="Academic Discussion\\n(academic_discussion)", shape=box, style="rounded,filled", fillcolor="#ffffff"];')
    lines.append('  END [label="END", shape=doublecircle, style="filled", fillcolor="#e2f0ff"];')

    # 主干边
    lines.append('  START -> router;')
    lines.append('  router -> chat [label="快速闲聊命中", fontsize=11];')
    lines.append('  router -> lit [label="mode=auto-search", fontsize=11];')
    lines.append('  router -> disc [label="mode=chat&plan", fontsize=11];')
    lines.append('  chat -> END [label="对话完成", fontsize=11];')

    # literature_search 分支
    lines.append('  lit -> exec [label="should_search=True 且 allow_search=True", fontsize=11, color="#0ea5e9"];')
    lines.append('  lit -> END [label="wait_decision / 条件不满足", fontsize=11, style=dashed, color="#64748b"];')

    # 搜索执行与结果
    lines.append('  exec -> fmt;')
    lines.append('  fmt -> END;')

    # 学术探讨
    lines.append('  disc -> END [label="默认结束（分析先行）", fontsize=11];')
    lines.append('  disc -> exec [label="(后台) auto-search + 建议搜索 → 由后端触发", fontsize=11, style=dotted, color="#94a3b8"];')

    # 图例
    lines.append('  subgraph cluster_legend {')
    lines.append('    label="图例"; fontsize=12; color="#94a3b8";')
    legend = (
        "圆角方框：处理节点\\n"
        "圆圈：开始/结束\\n"
        "蓝色边：auto-search 条件满足→图内检索\\n"
        "灰色虚线：等待/非图内路径（后端SSE触发）"
    )
    lines.append(f'    legend1 [label="{legend}", shape=note, style=filled, fillcolor="#f8fafc"];')
    lines.append('  }')

    lines.append("}")
    return "\n".join(lines)


if GRAPHVIZ_AVAILABLE:
    from graphviz import Digraph

    dot = Digraph("VeritexAgent", format="svg")
    dot.attr(rankdir="LR", labelloc="t", fontsize="14", label="Veritex Agent 工作流（LangGraph 状态机）")

    # 核心节点
    dot.node("START", "START", shape="circle", style="filled", fillcolor="#e2f0ff")
    dot.node("router", "模式路由\n(route_by_mode)\n+ 快速闲聊过滤", shape="box", style="rounded,filled", fillcolor="#ffffff")
    dot.node("chat", "Chat Conversation\n(chat_conversation)", shape="box", style="rounded,filled", fillcolor="#ffffff")
    dot.node("lit", "Literature Search\n(literature_search)\n仅分析 + 关键词扩展（缓存）", shape="box", style="rounded,filled", fillcolor="#ffffff")
    dot.node("exec", "Search Execution\n(search_execution)\n多源并行检索", shape="box", style="rounded,filled", fillcolor="#ffffff")
    dot.node("fmt", "Result Formatting\n(result_formatting)", shape="box", style="rounded,filled", fillcolor="#ffffff")
    dot.node("disc", "Academic Discussion\n(academic_discussion)", shape="box", style="rounded,filled", fillcolor="#ffffff")
    dot.node("END", "END", shape="doublecircle", style="filled", fillcolor="#e2f0ff")

    # 主干边
    dot.edge("START", "router")
    dot.edge("router", "chat", label="快速闲聊命中", fontsize="11")
    dot.edge("router", "lit", label="mode=auto-search", fontsize="11")
    dot.edge("router", "disc", label="mode=chat&plan", fontsize="11")
    dot.edge("chat", "END", label="对话完成", fontsize="11")

    # literature_search 分支
    dot.edge("lit", "exec", label="should_search=True 且 allow_search=True", fontsize="11", color="#0ea5e9")
    dot.edge("lit", "END", label="wait_decision / 条件不满足", fontsize="11", style="dashed", color="#64748b")

    # 搜索执行与结果
    dot.edge("exec", "fmt")
    dot.edge("fmt", "END")

    # 学术探讨
    dot.edge("disc", "END", label="默认结束（分析先行）", fontsize="11")
    dot.edge("disc", "exec", label="(后台) auto-search + 建议搜索 → 由后端触发", fontsize="11", style="dotted", color="#94a3b8")

    # 说明节点（图例）
    with dot.subgraph(name="cluster_legend") as c:
        c.attr(label="图例", fontsize="12", color="#94a3b8")
        c.node(
            "legend1",
            "圆角方框：处理节点\n圆圈：开始/结束\n蓝色边：auto-search 条件满足→图内检索\n灰色虚线：等待/非图内路径（后端SSE触发）",
            shape="note",
            style="filled",
            fillcolor="#f8fafc",
        )

    # 输出：优先渲染SVG；若失败，保存DOT
    try:
        outpath = dot.render(filename="langchain_workflows/agent_workflow", cleanup=True)
        print(f"✅ 生成完成：{outpath}")
    except Exception as e:
        dot.save(filename="langchain_workflows/agent_workflow.dot")
        print(f"⚠️ Graphviz 渲染失败，仅保存 DOT 文件：langchain_workflows/agent_workflow.dot — {e}")
else:
    # 纯文本构建DOT
    dot_src = build_dot_source()
    out_dot = "langchain_workflows/agent_workflow.dot"
    with open(out_dot, "w", encoding="utf-8") as f:
        f.write(dot_src)
    print(f"⚠️ 未检测到 graphviz Python 包，已保存 DOT 文件：{out_dot}")
