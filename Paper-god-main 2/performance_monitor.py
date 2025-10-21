"""
简化的性能监控模块
替代原有的复杂性能监控，专注核心功能
"""
import time
import threading
from typing import Dict, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """简化的性能监控器"""
    
    def __init__(self):
        self.stats = defaultdict(list)
        self.lock = threading.Lock()
    
    def record_chat_performance(self, duration: float, model: str, success: bool = True):
        """记录聊天性能"""
        with self.lock:
            self.stats['chat_requests'].append({
                'duration': duration,
                'model': model,
                'success': success,
                'timestamp': time.time()
            })
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        with self.lock:
            chat_requests = self.stats.get('chat_requests', [])
            
            if not chat_requests:
                return {
                    'total_requests': 0,
                    'average_duration': 0,
                    'success_rate': 0,
                    'last_24h_requests': 0
                }
            
            # 计算基本统计
            total_requests = len(chat_requests)
            durations = [req['duration'] for req in chat_requests]
            successes = [req for req in chat_requests if req['success']]
            
            # 24小时内的请求
            current_time = time.time()
            last_24h = [req for req in chat_requests 
                       if current_time - req['timestamp'] <= 86400]
            
            return {
                'total_requests': total_requests,
                'average_duration': sum(durations) / len(durations) if durations else 0,
                'success_rate': len(successes) / total_requests if total_requests else 0,
                'last_24h_requests': len(last_24h)
            }

# 全局监控器实例
_monitor = PerformanceMonitor()

def track_chat_performance(duration: float, model: str, success: bool = True):
    """记录聊天性能的装饰器函数"""
    _monitor.record_chat_performance(duration, model, success)

def get_performance_monitor():
    """获取性能监控器实例"""
    return _monitor