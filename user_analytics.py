"""
用户数据分析和监测模块
提供用户行为分析、数据统计和监测功能
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from supabase import create_client, Client
from collections import defaultdict, Counter

class UserAnalytics:
    """用户数据分析类"""
    
    def __init__(self):
        """初始化Supabase客户端"""
        self.supabase_url = "https://jfzchljmfnnsrszabpys.supabase.co"
        self.supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpmemNobGptZm5uc3JzemFicHlzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI2NDcwOTksImV4cCI6MjA2ODIyMzA5OX0.E_soKX6nkQm5xb4bO-q_4NmR8Z7ajQOQSq5cGtO91-g"
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
    
    def get_user_stats(self) -> Dict[str, Any]:
        """获取用户统计数据"""
        try:
            # 总用户数
            users_result = self.supabase.table('users').select('*').execute()
            total_users = len(users_result.data)
            
            # 邀请码使用情况
            invite_codes_result = self.supabase.table('invite_codes').select('*').execute()
            invite_codes = invite_codes_result.data
            used_codes = sum(1 for code in invite_codes if code['used'])
            unused_codes = len(invite_codes) - used_codes
            
            # 今日新增用户
            today = datetime.now().date()
            today_users = [user for user in users_result.data 
                         if datetime.fromisoformat(user['created_at'].replace('Z', '+00:00')).date() == today]
            
            # 最近7天用户活跃度
            seven_days_ago = datetime.now() - timedelta(days=7)
            active_users = [user for user in users_result.data 
                          if user['last_action_at'] and 
                          datetime.fromisoformat(user['last_action_at'].replace('Z', '+00:00')) >= seven_days_ago]
            
            return {
                'total_users': total_users,
                'today_new_users': len(today_users),
                'active_users_7d': len(active_users),
                'used_invite_codes': used_codes,
                'unused_invite_codes': unused_codes,
                'total_invite_codes': len(invite_codes),
                'code_usage_rate': f"{(used_codes/len(invite_codes)*100):.1f}%" if invite_codes else "0%"
            }
        except Exception as e:
            print(f"获取用户统计失败: {e}")
            return {}
    
    def get_user_actions_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取用户行为统计"""
        try:
            # 获取指定天数内的行为记录
            start_date = datetime.now() - timedelta(days=days)
            actions_result = self.supabase.table('user_actions').select('*').execute()
            
            # 过滤最近的行为记录
            recent_actions = [
                action for action in actions_result.data
                if datetime.fromisoformat(action['created_at'].replace('Z', '+00:00')) >= start_date
            ]
            
            # 行为类型统计
            action_types = Counter(action['action'] for action in recent_actions)
            
            # 按日期分组统计
            daily_stats = defaultdict(lambda: defaultdict(int))
            for action in recent_actions:
                date = datetime.fromisoformat(action['created_at'].replace('Z', '+00:00')).date()
                daily_stats[str(date)][action['action']] += 1
            
            # 最活跃用户
            user_activity = defaultdict(int)
            for action in recent_actions:
                user_activity[action['user_id']] += 1
            
            most_active_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'total_actions': len(recent_actions),
                'action_types': dict(action_types),
                'daily_stats': dict(daily_stats),
                'most_active_users': most_active_users,
                'analysis_period': f"最近{days}天"
            }
        except Exception as e:
            print(f"获取用户行为统计失败: {e}")
            return {}
    
    def get_search_analytics(self) -> Dict[str, Any]:
        """获取搜索行为分析"""
        try:
            # 获取所有搜索相关的行为
            search_actions = self.supabase.table('user_actions').select('*').eq('action', 'search_papers').execute()
            expand_actions = self.supabase.table('user_actions').select('*').eq('action', 'expand_keywords').execute()
            
            # 搜索关键词分析
            search_keywords = []
            for action in search_actions.data:
                if action['detail']:
                    keywords = [kw.strip() for kw in action['detail'].split(',')]
                    search_keywords.extend(keywords)
            
            # 扩展关键词分析
            expand_keywords = []
            for action in expand_actions.data:
                if action['detail']:
                    expand_keywords.append(action['detail'].strip())
            
            # 热门关键词
            popular_search_keywords = Counter(search_keywords).most_common(20)
            popular_expand_keywords = Counter(expand_keywords).most_common(20)
            
            return {
                'total_searches': len(search_actions.data),
                'total_expansions': len(expand_actions.data),
                'unique_search_keywords': len(set(search_keywords)),
                'unique_expand_keywords': len(set(expand_keywords)),
                'popular_search_keywords': popular_search_keywords,
                'popular_expand_keywords': popular_expand_keywords
            }
        except Exception as e:
            print(f"获取搜索分析失败: {e}")
            return {}
    
    def get_user_timeline(self, user_id: str, limit: int = 50) -> List[Dict]:
        """获取用户时间线"""
        try:
            # 获取用户信息
            user_result = self.supabase.table('users').select('*').eq('id', user_id).single().execute()
            
            # 获取用户行为记录
            actions_result = (self.supabase.table('user_actions')
                            .select('*')
                            .eq('user_id', user_id)
                            .order('created_at', desc=True)
                            .limit(limit)
                            .execute())
            
            # 格式化时间线
            timeline = []
            for action in actions_result.data:
                timeline.append({
                    'timestamp': action['created_at'],
                    'action': action['action'],
                    'detail': action['detail'],
                    'formatted_time': datetime.fromisoformat(action['created_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return {
                'user_info': user_result.data,
                'timeline': timeline,
                'total_actions': len(actions_result.data)
            }
        except Exception as e:
            print(f"获取用户时间线失败: {e}")
            return {}
    
    async def log_user_action(self, user_id: str, action: str, detail: str = None) -> bool:
        """记录用户行为"""
        try:
            # 插入行为记录
            self.supabase.table('user_actions').insert({
                'user_id': user_id,
                'action': action,
                'detail': detail,
                'created_at': datetime.now().isoformat()
            }).execute()
            
            # 更新用户最后活动时间
            self.supabase.table('users').update({
                'last_action_at': datetime.now().isoformat()
            }).eq('id', user_id).execute()
            
            return True
        except Exception as e:
            print(f"记录用户行为失败: {e}")
            return False
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """获取实时统计数据"""
        try:
            # 当前在线用户（最近5分钟有活动）
            five_minutes_ago = datetime.now() - timedelta(minutes=5)
            
            # 获取最近活跃的用户
            users_result = self.supabase.table('users').select('*').execute()
            recent_active_users = [
                user for user in users_result.data
                if user['last_action_at'] and 
                datetime.fromisoformat(user['last_action_at'].replace('Z', '+00:00')) >= five_minutes_ago
            ]
            
            # 今日统计
            today = datetime.now().date()
            today_actions = self.supabase.table('user_actions').select('*').execute()
            today_actions_filtered = [
                action for action in today_actions.data
                if datetime.fromisoformat(action['created_at'].replace('Z', '+00:00')).date() == today
            ]
            
            # 最近1小时的活动
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_actions = [
                action for action in today_actions.data
                if datetime.fromisoformat(action['created_at'].replace('Z', '+00:00')) >= one_hour_ago
            ]
            
            return {
                'current_active_users': len(recent_active_users),
                'today_total_actions': len(today_actions_filtered),
                'last_hour_actions': len(recent_actions),
                'recent_active_users': [
                    {
                        'user_id': user['id'],
                        'invite_code': user['invite_code'],
                        'last_action': user['last_action'],
                        'last_action_time': user['last_action_at']
                    }
                    for user in recent_active_users[:10]
                ],
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"获取实时统计失败: {e}")
            return {}
    
    def generate_daily_report(self, date: Optional[str] = None) -> Dict[str, Any]:
        """生成每日报告"""
        if date is None:
            date = datetime.now().date()
        else:
            date = datetime.fromisoformat(date).date()
        
        try:
            # 获取指定日期的数据
            start_datetime = datetime.combine(date, datetime.min.time())
            end_datetime = datetime.combine(date, datetime.max.time())
            
            # 当日新增用户
            users_result = self.supabase.table('users').select('*').execute()
            new_users = [
                user for user in users_result.data
                if datetime.fromisoformat(user['created_at'].replace('Z', '+00:00')).date() == date
            ]
            
            # 当日用户行为
            actions_result = self.supabase.table('user_actions').select('*').execute()
            daily_actions = [
                action for action in actions_result.data
                if datetime.fromisoformat(action['created_at'].replace('Z', '+00:00')).date() == date
            ]
            
            # 行为类型统计
            action_types = Counter(action['action'] for action in daily_actions)
            
            # 活跃用户
            active_users = list(set(action['user_id'] for action in daily_actions))
            
            return {
                'date': str(date),
                'new_users': len(new_users),
                'total_actions': len(daily_actions),
                'active_users': len(active_users),
                'action_breakdown': dict(action_types),
                'new_user_details': [
                    {
                        'user_id': user['id'],
                        'invite_code': user['invite_code'],
                        'created_at': user['created_at']
                    }
                    for user in new_users
                ]
            }
        except Exception as e:
            print(f"生成每日报告失败: {e}")
            return {}

def main():
    """主函数 - 用于测试和演示"""
    analytics = UserAnalytics()
    
    print("=== 用户数据监测报告 ===")
    print("\n1. 用户统计:")
    user_stats = analytics.get_user_stats()
    for key, value in user_stats.items():
        print(f"  {key}: {value}")
    
    print("\n2. 用户行为统计 (最近7天):")
    action_stats = analytics.get_user_actions_stats(7)
    for key, value in action_stats.items():
        if key != 'daily_stats':
            print(f"  {key}: {value}")
    
    print("\n3. 搜索行为分析:")
    search_analytics = analytics.get_search_analytics()
    for key, value in search_analytics.items():
        if 'popular' not in key:
            print(f"  {key}: {value}")
    
    print("\n4. 实时统计:")
    real_time = analytics.get_real_time_stats()
    for key, value in real_time.items():
        if key != 'recent_active_users':
            print(f"  {key}: {value}")
    
    print("\n5. 今日报告:")
    daily_report = analytics.generate_daily_report()
    for key, value in daily_report.items():
        if key != 'new_user_details':
            print(f"  {key}: {value}")

if __name__ == "__main__":
    main()