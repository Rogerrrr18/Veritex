"""
性能监控工具 - 跟踪聊天接口的性能指标
"""
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    request_type: str  # "fast_chat", "complex_chat", "academic_search"
    response_time: float  # 总响应时间（秒）
    llm_calls: int  # LLM调用次数
    is_fast_path: bool  # 是否走快速路径
    workflow_time: Optional[float] = None  # 工作流耗时
    token_count: Optional[int] = None  # Token使用量
    error_occurred: bool = False  # 是否发生错误

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics_history = []
        self.stats = defaultdict(list)
        
    def track_request(self, metrics: PerformanceMetrics):
        """记录一次请求的性能指标"""
        self.metrics_history.append(metrics)
        self.stats[metrics.request_type].append(metrics.response_time)
        
        # 记录性能日志
        if metrics.is_fast_path:
            self.logger.info(
                f"⚡ 快速响应 - 类型: {metrics.request_type}, "
                f"耗时: {metrics.response_time:.3f}s, "
                f"LLM调用: {metrics.llm_calls}次"
            )
        else:
            self.logger.info(
                f"🕰️ 常规响应 - 类型: {metrics.request_type}, "
                f"总耗时: {metrics.response_time:.3f}s, "
                f"工作流耗时: {metrics.workflow_time:.3f}s, "
                f"LLM调用: {metrics.llm_calls}次"
            )
        
        # 如果响应时间过长，记录警告
        if metrics.response_time > 5.0:
            self.logger.warning(
                f"⚠️ 响应时间过长: {metrics.response_time:.3f}s, "
                f"类型: {metrics.request_type}"
            )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能统计摘要"""
        if not self.metrics_history:
            return {"message": "暂无性能数据"}
        
        # 计算各类型请求的统计
        summary = {}
        for request_type in self.stats:
            times = self.stats[request_type]
            if times:
                summary[request_type] = {
                    "count": len(times),
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times)
                }
        
        # 统计快速路径使用率
        fast_path_count = sum(1 for m in self.metrics_history if m.is_fast_path)
        total_count = len(self.metrics_history)
        
        # 统计LLM调用
        total_llm_calls = sum(m.llm_calls for m in self.metrics_history)
        avg_llm_calls = total_llm_calls / total_count if total_count > 0 else 0
        
        summary["overall"] = {
            "total_requests": total_count,
            "fast_path_rate": fast_path_count / total_count if total_count > 0 else 0,
            "avg_response_time": sum(m.response_time for m in self.metrics_history) / total_count if total_count > 0 else 0,
            "total_llm_calls": total_llm_calls,
            "avg_llm_calls_per_request": avg_llm_calls,
            "error_rate": sum(1 for m in self.metrics_history if m.error_occurred) / total_count if total_count > 0 else 0
        }
        
        return summary
    
    def reset_stats(self):
        """重置统计数据"""
        self.metrics_history.clear()
        self.stats.clear()
        self.logger.info("📊 性能统计数据已重置")

# 全局性能监控实例
_performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor

def create_performance_context():
    """创建性能监控上下文管理器"""
    class PerformanceContext:
        def __init__(self):
            self.start_time = None
            self.monitor = get_performance_monitor()
            
        def __enter__(self):
            self.start_time = time.time()
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            response_time = time.time() - self.start_time
            
            # 根据异常情况记录错误
            error_occurred = exc_type is not None
            
            # 这里可以根据需要创建默认指标
            metrics = PerformanceMetrics(
                request_type="unknown",
                response_time=response_time,
                llm_calls=0,
                is_fast_path=False,
                error_occurred=error_occurred
            )
            
            self.monitor.track_request(metrics)
    
    return PerformanceContext()

# 便捷函数
def track_chat_performance(
    request_type: str,
    response_time: float,
    llm_calls: int,
    is_fast_path: bool = False,
    workflow_time: Optional[float] = None,
    token_count: Optional[int] = None,
    error_occurred: bool = False
):
    """便捷的性能跟踪函数"""
    metrics = PerformanceMetrics(
        request_type=request_type,
        response_time=response_time,
        llm_calls=llm_calls,
        is_fast_path=is_fast_path,
        workflow_time=workflow_time,
        token_count=token_count,
        error_occurred=error_occurred
    )
    
    monitor = get_performance_monitor()
    monitor.track_request(metrics)
    
    return metrics