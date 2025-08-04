"""
LangGraph工作流实时监控模块
提供WebSocket实时推送、状态管理、性能监控等功能
"""
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Callable, AsyncIterator
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
import weakref

@dataclass
class NodeExecutionMetrics:
    """节点执行指标"""
    node_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    status: str = "running"  # running, completed, error, timeout
    error_message: Optional[str] = None
    input_size: int = 0
    output_size: int = 0
    memory_usage: float = 0.0
    
    def complete(self, status: str = "completed", error_message: str = None):
        """标记节点执行完成"""
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.status = status
        if error_message:
            self.error_message = error_message

@dataclass
class WorkflowExecutionStats:
    """工作流执行统计"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: Optional[float] = None
    nodes_executed: int = 0
    nodes_completed: int = 0
    nodes_failed: int = 0
    total_memory_peak: float = 0.0
    success_rate: float = 0.0
    
    def calculate_stats(self, metrics: List[NodeExecutionMetrics]):
        """计算统计数据"""
        self.nodes_executed = len(metrics)
        self.nodes_completed = len([m for m in metrics if m.status == "completed"])
        self.nodes_failed = len([m for m in metrics if m.status == "error"])
        
        if self.nodes_executed > 0:
            self.success_rate = self.nodes_completed / self.nodes_executed
        
        if metrics and all(m.end_time for m in metrics):
            self.end_time = max(m.end_time for m in metrics if m.end_time)
            self.total_duration = (self.end_time - self.start_time).total_seconds()


class WorkflowMonitor:
    """
    工作流监控器
    负责实时监控、指标收集、状态管理
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_time = datetime.now()
        self.node_metrics: Dict[str, NodeExecutionMetrics] = {}
        self.execution_history: deque = deque(maxlen=1000)  # 最多保存1000条记录
        self.subscribers: List[Callable[[Dict], None]] = []
        self.is_active = True
        self.lock = threading.Lock()
        
        # 性能监控
        self.performance_samples = defaultdict(list)
        self.alert_thresholds = {
            "node_timeout": 300.0,  # 5分钟
            "memory_threshold": 1024.0,  # 1GB
            "error_rate": 0.3  # 30%
        }
        
    def start_node_execution(self, node_name: str, input_data: Any = None) -> str:
        """开始监控节点执行"""
        with self.lock:
            metric = NodeExecutionMetrics(
                node_name=node_name,
                start_time=datetime.now(),
                input_size=len(str(input_data)) if input_data else 0
            )
            
            self.node_metrics[node_name] = metric
            self.execution_history.append({
                "type": "node_start",
                "timestamp": metric.start_time.isoformat(),
                "node_name": node_name,
                "session_id": self.session_id
            })
            
            # 通知订阅者
            self._notify_subscribers({
                "event": "node_started",
                "session_id": self.session_id,
                "node_name": node_name,
                "timestamp": metric.start_time.isoformat()
            })
            
            print(f"🚀 [{self.session_id}] 开始执行节点: {node_name}")
            return node_name
    
    def complete_node_execution(self, node_name: str, 
                               status: str = "completed", 
                               output_data: Any = None,
                               error_message: str = None):
        """完成节点执行监控"""
        with self.lock:
            if node_name not in self.node_metrics:
                print(f"⚠️ 警告: 节点 {node_name} 没有开始监控记录")
                return
            
            metric = self.node_metrics[node_name]
            metric.complete(status, error_message)
            metric.output_size = len(str(output_data)) if output_data else 0
            
            # 记录到执行历史
            self.execution_history.append({
                "type": "node_complete",
                "timestamp": metric.end_time.isoformat(),
                "node_name": node_name,
                "status": status,
                "duration": metric.duration,
                "session_id": self.session_id,
                "error": error_message
            })
            
            # 性能采样
            self.performance_samples[node_name].append({
                "duration": metric.duration,
                "timestamp": metric.end_time,
                "memory": metric.memory_usage
            })
            
            # 检查告警
            self._check_alerts(metric)
            
            # 通知订阅者
            self._notify_subscribers({
                "event": "node_completed",
                "session_id": self.session_id,
                "node_name": node_name,
                "status": status,
                "duration": metric.duration,
                "error": error_message,
                "timestamp": metric.end_time.isoformat()
            })
            
            status_icon = {"completed": "✅", "error": "❌", "timeout": "⏰"}.get(status, "📍")
            print(f"{status_icon} [{self.session_id}] 节点完成: {node_name} ({metric.duration:.2f}s)")
            
            if error_message:
                print(f"   ❌ 错误: {error_message}")
    
    def update_node_progress(self, node_name: str, progress: float, message: str = None):
        """更新节点进度"""
        with self.lock:
            # 通知订阅者
            self._notify_subscribers({
                "event": "node_progress",
                "session_id": self.session_id,
                "node_name": node_name,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            
            print(f"🔄 [{self.session_id}] {node_name}: {progress:.1%} - {message or ''}")
    
    def subscribe(self, callback: Callable[[Dict], None]):
        """订阅监控事件"""
        self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[Dict], None]):
        """取消订阅"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def _notify_subscribers(self, event_data: Dict):
        """通知所有订阅者"""
        for callback in self.subscribers:
            try:
                callback(event_data)
            except Exception as e:
                print(f"⚠️ 订阅者通知失败: {e}")
    
    def _check_alerts(self, metric: NodeExecutionMetrics):
        """检查告警条件"""
        # 超时告警
        if metric.duration and metric.duration > self.alert_thresholds["node_timeout"]:
            self._send_alert("timeout", f"节点 {metric.node_name} 执行超时: {metric.duration:.2f}s")
        
        # 内存告警
        if metric.memory_usage > self.alert_thresholds["memory_threshold"]:
            self._send_alert("memory", f"节点 {metric.node_name} 内存使用过高: {metric.memory_usage:.2f}MB")
        
        # 错误率告警
        recent_metrics = list(self.node_metrics.values())[-10:]  # 最近10个节点
        if len(recent_metrics) >= 5:
            error_rate = len([m for m in recent_metrics if m.status == "error"]) / len(recent_metrics)
            if error_rate > self.alert_thresholds["error_rate"]:
                self._send_alert("error_rate", f"错误率过高: {error_rate:.1%}")
    
    def _send_alert(self, alert_type: str, message: str):
        """发送告警"""
        alert_data = {
            "event": "alert",
            "session_id": self.session_id,
            "alert_type": alert_type,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        self._notify_subscribers(alert_data)
        print(f"🚨 [{self.session_id}] 告警: {message}")
    
    def get_current_stats(self) -> WorkflowExecutionStats:
        """获取当前统计数据"""
        with self.lock:
            stats = WorkflowExecutionStats(
                session_id=self.session_id,
                start_time=self.start_time
            )
            
            metrics_list = list(self.node_metrics.values())
            stats.calculate_stats(metrics_list)
            
            return stats
    
    def get_node_performance(self, node_name: str) -> Dict[str, Any]:
        """获取节点性能数据"""
        samples = self.performance_samples.get(node_name, [])
        if not samples:
            return {"node_name": node_name, "sample_count": 0}
        
        durations = [s["duration"] for s in samples if s["duration"]]
        
        return {
            "node_name": node_name,
            "sample_count": len(samples),
            "avg_duration": sum(durations) / len(durations) if durations else 0,
            "min_duration": min(durations) if durations else 0,
            "max_duration": max(durations) if durations else 0,
            "latest_duration": durations[-1] if durations else 0
        }
    
    def export_monitoring_data(self) -> Dict[str, Any]:
        """导出监控数据"""
        with self.lock:
            return {
                "session_id": self.session_id,
                "start_time": self.start_time.isoformat(),
                "node_metrics": {
                    name: asdict(metric) for name, metric in self.node_metrics.items()
                },
                "execution_history": list(self.execution_history),
                "performance_samples": dict(self.performance_samples),
                "stats": asdict(self.get_current_stats())
            }
    
    def cleanup(self):
        """清理监控器资源"""
        self.is_active = False
        self.subscribers.clear()
        print(f"🧹 [{self.session_id}] 监控器已清理")


class WorkflowMonitorManager:
    """
    工作流监控管理器
    管理多个监控器实例，提供全局监控视图
    """
    
    def __init__(self):
        self.monitors: Dict[str, WorkflowMonitor] = {}
        self.global_subscribers: List[Callable[[Dict], None]] = []
        self.lock = threading.Lock()
    
    def create_monitor(self, session_id: str) -> WorkflowMonitor:
        """创建新的监控器"""
        with self.lock:
            if session_id in self.monitors:
                print(f"⚠️ 警告: 监控器 {session_id} 已存在，将被替换")
                self.monitors[session_id].cleanup()
            
            monitor = WorkflowMonitor(session_id)
            
            # 订阅监控器事件，转发给全局订阅者
            monitor.subscribe(self._forward_to_global_subscribers)
            
            self.monitors[session_id] = monitor
            print(f"📊 创建监控器: {session_id}")
            
            return monitor
    
    def get_monitor(self, session_id: str) -> Optional[WorkflowMonitor]:
        """获取监控器"""
        return self.monitors.get(session_id)
    
    def remove_monitor(self, session_id: str):
        """移除监控器"""
        with self.lock:
            if session_id in self.monitors:
                self.monitors[session_id].cleanup()
                del self.monitors[session_id]
                print(f"🗑️ 移除监控器: {session_id}")
    
    def subscribe_global(self, callback: Callable[[Dict], None]):
        """订阅全局监控事件"""
        self.global_subscribers.append(callback)
    
    def _forward_to_global_subscribers(self, event_data: Dict):
        """转发事件给全局订阅者"""
        for callback in self.global_subscribers:
            try:
                callback(event_data)
            except Exception as e:
                print(f"⚠️ 全局订阅者通知失败: {e}")
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有监控器的统计数据"""
        with self.lock:
            return {
                session_id: asdict(monitor.get_current_stats())
                for session_id, monitor in self.monitors.items()
            }
    
    async def stream_global_events(self) -> AsyncIterator[Dict]:
        """流式输出全局监控事件"""
        event_queue = asyncio.Queue()
        
        def queue_event(event_data):
            try:
                event_queue.put_nowait(event_data)
            except asyncio.QueueFull:
                print("⚠️ 事件队列已满，丢弃事件")
        
        self.subscribe_global(queue_event)
        
        try:
            while True:
                event = await event_queue.get()
                yield event
        except asyncio.CancelledError:
            print("🛑 全局事件流已取消")
        finally:
            if queue_event in self.global_subscribers:
                self.global_subscribers.remove(queue_event)


# 全局监控管理器实例
_global_monitor_manager = WorkflowMonitorManager()

def get_monitor_manager() -> WorkflowMonitorManager:
    """获取全局监控管理器"""
    return _global_monitor_manager

def create_workflow_monitor(session_id: str) -> WorkflowMonitor:
    """创建工作流监控器"""
    return _global_monitor_manager.create_monitor(session_id)

def get_workflow_monitor(session_id: str) -> Optional[WorkflowMonitor]:
    """获取工作流监控器"""
    return _global_monitor_manager.get_monitor(session_id)


# 监控装饰器
def monitor_node_execution(session_id: str, node_name: str = None):
    """
    节点执行监控装饰器
    
    Usage:
        @monitor_node_execution("session_123", "search_papers")
        async def search_papers_node(state):
            # 节点逻辑
            return updated_state
    """
    def decorator(func):
        actual_node_name = node_name or func.__name__
        
        async def async_wrapper(*args, **kwargs):
            monitor = get_workflow_monitor(session_id)
            if not monitor:
                print(f"⚠️ 警告: 未找到监控器 {session_id}")
                return await func(*args, **kwargs)
            
            monitor.start_node_execution(actual_node_name, args[0] if args else None)
            
            try:
                result = await func(*args, **kwargs)
                monitor.complete_node_execution(actual_node_name, "completed", result)
                return result
            except Exception as e:
                monitor.complete_node_execution(actual_node_name, "error", None, str(e))
                raise
        
        def sync_wrapper(*args, **kwargs):
            monitor = get_workflow_monitor(session_id)
            if not monitor:
                print(f"⚠️ 警告: 未找到监控器 {session_id}")
                return func(*args, **kwargs)
            
            monitor.start_node_execution(actual_node_name, args[0] if args else None)
            
            try:
                result = func(*args, **kwargs)
                monitor.complete_node_execution(actual_node_name, "completed", result)
                return result
            except Exception as e:
                monitor.complete_node_execution(actual_node_name, "error", None, str(e))
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


if __name__ == "__main__":
    # 演示监控功能
    print("🔍 工作流监控演示")
    
    # 创建监控器
    monitor = create_workflow_monitor("demo_session")
    
    # 订阅事件
    def print_event(event):
        print(f"📢 事件: {json.dumps(event, ensure_ascii=False, indent=2)}")
    
    monitor.subscribe(print_event)
    
    # 模拟节点执行
    import time
    
    nodes = ["analyze_query", "search_papers", "process_results", "generate_response"]
    
    for i, node in enumerate(nodes):
        monitor.start_node_execution(node, f"input_data_{i}")
        
        # 模拟执行时间和进度更新
        for progress in [0.3, 0.6, 1.0]:
            time.sleep(0.2)
            monitor.update_node_progress(node, progress, f"处理中...{progress:.0%}")
        
        # 模拟完成（最后一个节点可能出错）
        if i == len(nodes) - 1 and False:  # 模拟错误
            monitor.complete_node_execution(node, "error", None, "模拟错误")
        else:
            monitor.complete_node_execution(node, "completed", f"output_data_{i}")
    
    # 显示统计数据
    stats = monitor.get_current_stats()
    print(f"\n📊 统计数据: {json.dumps(asdict(stats), ensure_ascii=False, indent=2)}")
    
    # 清理
    monitor.cleanup()