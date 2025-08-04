#!/usr/bin/env python3
"""
LangGraph工作流CLI监控工具
提供命令行界面的实时监控和可视化功能
"""
import asyncio
import argparse
import json
import time
import sys
import os
from typing import Dict, Any, Optional
from datetime import datetime
import websockets
import requests
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.align import Align

console = Console()

class CLIMonitor:
    """命令行监控器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = None
        self.monitoring_active = False
        self.stats = {}
        self.recent_events = []
        self.node_status = {}
        
    def display_banner(self):
        """显示欢迎横幅"""
        banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                          🔍 LangGraph 工作流监控工具                         ║
║                        基于CLI的实时监控和可视化系统                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        console.print(banner, style="bold blue")
    
    def get_workflow_visualization(self) -> str:
        """获取工作流ASCII可视化"""
        try:
            response = requests.get(f"{self.base_url}/visualization/workflow")
            if response.status_code == 200:
                data = response.json()
                return data.get("ascii_flow", "可视化数据不可用")
            else:
                return f"❌ 获取可视化失败: {response.status_code}"
        except Exception as e:
            return f"❌ 连接失败: {str(e)}"
    
    def display_workflow(self):
        """显示工作流结构"""
        console.print("\n📊 工作流结构:", style="bold green")
        workflow_ascii = self.get_workflow_visualization()
        console.print(Panel(workflow_ascii, title="LangGraph 论文搜索工作流", border_style="blue"))
    
    def create_stats_table(self) -> Table:
        """创建统计数据表格"""
        table = Table(title="📈 实时统计数据", show_header=True, header_style="bold magenta")
        table.add_column("指标", style="cyan", width=20)
        table.add_column("数值", style="green", width=15)
        table.add_column("状态", style="yellow", width=15)
        
        stats = self.stats.get("stats", {})
        
        table.add_row("会话ID", self.session_id or "未设置", "🔧")
        table.add_row("已执行节点", str(stats.get("nodes_executed", 0)), "📊")
        table.add_row("完成的节点", str(stats.get("nodes_completed", 0)), "✅")
        table.add_row("失败的节点", str(stats.get("nodes_failed", 0)), "❌")
        
        success_rate = stats.get("success_rate", 0)
        success_percentage = f"{success_rate * 100:.1f}%" if success_rate else "0%"
        success_icon = "🟢" if success_rate > 0.8 else "🟡" if success_rate > 0.5 else "🔴"
        table.add_row("成功率", success_percentage, success_icon)
        
        return table
    
    def create_events_table(self) -> Table:
        """创建事件日志表格"""
        table = Table(title="📜 最近事件", show_header=True, header_style="bold cyan")
        table.add_column("时间", style="dim", width=12)
        table.add_column("类型", style="magenta", width=15)
        table.add_column("节点", style="blue", width=15)
        table.add_column("消息", style="white", width=40)
        
        for event in self.recent_events[-10:]:  # 显示最近10个事件
            event_time = event.get("timestamp", "")
            if event_time:
                try:
                    dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                    event_time = dt.strftime("%H:%M:%S")
                except:
                    event_time = event_time[:8]  # 取前8个字符
            
            event_type = event.get("type", "unknown")
            node_name = event.get("node_name", "-")
            message = event.get("message", str(event))[:38] + "..." if len(str(event)) > 40 else str(event)
            
            # 根据事件类型选择样式
            if "error" in event_type.lower():
                style = "red"
            elif "completed" in event_type.lower() or "success" in event_type.lower():
                style = "green"
            elif "started" in event_type.lower():
                style = "yellow"
            else:
                style = "white"
                
            table.add_row(event_time, event_type, node_name, message, style=style)
        
        return table
    
    def create_node_status_table(self) -> Table:
        """创建节点状态表格"""
        table = Table(title="🔧 节点状态", show_header=True, header_style="bold yellow")
        table.add_column("节点名称", style="cyan", width=20)
        table.add_column("状态", style="white", width=15)
        table.add_column("持续时间", style="magenta", width=15)
        
        for node_name, status_info in self.node_status.items():
            status = status_info.get("status", "unknown")
            duration = status_info.get("duration", 0)
            
            # 状态图标
            status_icons = {
                "running": "🔄",
                "completed": "✅",
                "error": "❌",
                "waiting": "⏳"
            }
            
            status_display = f"{status_icons.get(status, '📍')} {status}"
            duration_display = f"{duration:.2f}s" if duration else "-"
            
            table.add_row(node_name, status_display, duration_display)
        
        return table
    
    def create_layout(self) -> Layout:
        """创建终端布局"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        layout["left"].split_column(
            Layout(name="stats"),
            Layout(name="nodes")
        )
        
        layout["right"].split_column(
            Layout(name="events")
        )
        
        return layout
    
    def update_layout(self, layout: Layout):
        """更新布局内容"""
        # 头部
        header_text = Text.assemble(
            ("🔍 LangGraph 工作流监控 ", "bold blue"),
            (f"会话: {self.session_id or 'N/A'} ", "cyan"),
            (f"状态: {'🟢 监控中' if self.monitoring_active else '🔴 未连接'}", "green" if self.monitoring_active else "red"),
            (" | ", "dim"),
            (f"时间: {datetime.now().strftime('%H:%M:%S')}", "dim")
        )
        layout["header"].update(Align.center(header_text))
        
        # 统计数据
        layout["stats"].update(Panel(self.create_stats_table(), border_style="green"))
        
        # 节点状态
        layout["nodes"].update(Panel(self.create_node_status_table(), border_style="yellow"))
        
        # 事件日志
        layout["events"].update(Panel(self.create_events_table(), border_style="cyan"))
        
        # 底部
        footer_text = Text.assemble(
            ("按 Ctrl+C 退出 | ", "dim"),
            ("按 'h' 显示帮助 | ", "dim"),
            ("按 's' 开始搜索 | ", "dim"),
            ("按 'r' 刷新数据", "dim")
        )
        layout["footer"].update(Align.center(footer_text))
    
    async def websocket_monitor(self, session_id: str):
        """WebSocket监控"""
        uri = f"ws://localhost:8000/ws/{session_id}"
        
        try:
            async with websockets.connect(uri) as websocket:
                console.print(f"✅ WebSocket连接成功: {session_id}", style="green")
                self.monitoring_active = True
                
                # 请求初始统计数据
                await websocket.send(json.dumps({"type": "get_stats"}))
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.handle_websocket_message(data)
                    except json.JSONDecodeError:
                        console.print(f"⚠️ 无效的JSON消息: {message}", style="yellow")
                        
        except Exception as e:
            console.print(f"❌ WebSocket连接失败: {str(e)}", style="red")
            self.monitoring_active = False
    
    async def handle_websocket_message(self, data: Dict[str, Any]):
        """处理WebSocket消息"""
        message_type = data.get("type")
        
        if message_type == "stats_update":
            self.stats = data.get("data", {})
        elif message_type == "monitor_event":
            event_data = data.get("data", {})
            self.recent_events.append(event_data)
            
            # 更新节点状态
            node_name = event_data.get("node_name")
            if node_name:
                if node_name not in self.node_status:
                    self.node_status[node_name] = {}
                
                self.node_status[node_name].update({
                    "status": event_data.get("status", "unknown"),
                    "duration": event_data.get("duration"),
                    "last_update": datetime.now()
                })
        
        # 保持事件列表大小
        if len(self.recent_events) > 50:
            self.recent_events = self.recent_events[-50:]
    
    async def start_monitoring(self, session_id: str):
        """开始监控"""
        self.session_id = session_id
        console.print(f"🚀 开始监控会话: {session_id}", style="bold green")
        
        # 创建布局
        layout = self.create_layout()
        
        # 启动WebSocket监控任务
        monitor_task = asyncio.create_task(self.websocket_monitor(session_id))
        
        # 实时显示
        with Live(layout, refresh_per_second=2, screen=True) as live:
            try:
                while True:
                    self.update_layout(layout)
                    await asyncio.sleep(0.5)
                    
                    # 检查WebSocket任务状态
                    if monitor_task.done():
                        exception = monitor_task.exception()
                        if exception:
                            console.print(f"❌ 监控任务异常: {exception}", style="red")
                        break
                        
            except KeyboardInterrupt:
                console.print("\n👋 监控已停止", style="yellow")
                monitor_task.cancel()
    
    def start_search(self, query: str, session_id: str):
        """启动搜索"""
        try:
            response = requests.post(f"{self.base_url}/search", json={
                "query": query,
                "max_results": 10
            })
            
            if response.status_code == 200:
                result = response.json()
                console.print(f"✅ 搜索已启动: {result.get('session_id')}", style="green")
                return result.get('session_id')
            else:
                console.print(f"❌ 搜索启动失败: {response.status_code}", style="red")
                return None
                
        except Exception as e:
            console.print(f"❌ 搜索请求失败: {str(e)}", style="red")
            return None
    
    def interactive_mode(self):
        """交互模式"""
        while True:
            console.print("\n" + "="*60)
            console.print("🎮 交互模式菜单", style="bold cyan")
            console.print("1. 显示工作流结构")
            console.print("2. 开始实时监控")
            console.print("3. 启动论文搜索")
            console.print("4. 获取会话统计")
            console.print("5. 退出")
            
            choice = console.input("\n请选择操作 [1-5]: ")
            
            if choice == "1":
                self.display_workflow()
            elif choice == "2":
                session_id = console.input("请输入会话ID (默认: demo_session): ").strip() or "demo_session"
                try:
                    asyncio.run(self.start_monitoring(session_id))
                except KeyboardInterrupt:
                    console.print("\n监控已停止", style="yellow")
            elif choice == "3":
                query = console.input("请输入搜索查询: ").strip()
                if query:
                    session_id = console.input("请输入会话ID (默认: search_session): ").strip() or "search_session"
                    result_session = self.start_search(query, session_id)
                    if result_session:
                        console.print(f"搜索会话ID: {result_session}")
                        monitor = console.input("是否开始监控此会话? (y/N): ").strip().lower()
                        if monitor == 'y':
                            try:
                                asyncio.run(self.start_monitoring(result_session))
                            except KeyboardInterrupt:
                                console.print("\n监控已停止", style="yellow")
            elif choice == "4":
                session_id = console.input("请输入会话ID: ").strip()
                if session_id:
                    self.show_session_stats(session_id)
            elif choice == "5":
                console.print("👋 再见!", style="bold blue")
                break
            else:
                console.print("❌ 无效选择", style="red")
    
    def show_session_stats(self, session_id: str):
        """显示会话统计"""
        try:
            response = requests.get(f"{self.base_url}/monitoring/stats/{session_id}")
            if response.status_code == 200:
                stats = response.json()
                console.print(f"\n📊 会话 {session_id} 统计数据:", style="bold green")
                console.print(Panel(json.dumps(stats, ensure_ascii=False, indent=2), border_style="green"))
            else:
                console.print(f"❌ 获取统计失败: {response.status_code}", style="red")
        except Exception as e:
            console.print(f"❌ 请求失败: {str(e)}", style="red")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="LangGraph工作流CLI监控工具")
    parser.add_argument("--url", default="http://localhost:8000", help="后端服务URL")
    parser.add_argument("--session", help="直接监控指定会话ID")
    parser.add_argument("--search", help="启动搜索并监控")
    parser.add_argument("--workflow", action="store_true", help="仅显示工作流结构")
    
    args = parser.parse_args()
    
    monitor = CLIMonitor(args.url)
    monitor.display_banner()
    
    if args.workflow:
        monitor.display_workflow()
    elif args.search:
        session_id = monitor.start_search(args.search, "cli_search_session")
        if session_id:
            try:
                asyncio.run(monitor.start_monitoring(session_id))
            except KeyboardInterrupt:
                console.print("\n监控已停止", style="yellow")
    elif args.session:
        try:
            asyncio.run(monitor.start_monitoring(args.session))
        except KeyboardInterrupt:
            console.print("\n监控已停止", style="yellow")
    else:
        monitor.interactive_mode()


if __name__ == "__main__":
    main()