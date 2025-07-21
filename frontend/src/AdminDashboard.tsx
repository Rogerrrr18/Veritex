import React, { useState, useEffect } from 'react';

interface UserStats {
  total_users: number;
  today_new_users: number;
  active_users_7d: number;
  used_invite_codes: number;
  unused_invite_codes: number;
  total_invite_codes: number;
  code_usage_rate: string;
}

interface ActionStats {
  total_actions: number;
  action_types: { [key: string]: number };
  most_active_users: Array<[string, number]>;
  analysis_period: string;
}

interface SearchAnalytics {
  total_searches: number;
  total_expansions: number;
  unique_search_keywords: number;
  unique_expand_keywords: number;
  popular_search_keywords: Array<[string, number]>;
  popular_expand_keywords: Array<[string, number]>;
}

interface RealTimeStats {
  current_active_users: number;
  today_total_actions: number;
  last_hour_actions: number;
  recent_active_users: Array<{
    user_id: string;
    invite_code: string;
    last_action: string;
    last_action_time: string;
  }>;
  timestamp: string;
}

interface DashboardData {
  user_stats: UserStats;
  real_time_stats: RealTimeStats;
  action_stats: ActionStats;
  search_analytics: SearchAnalytics;
  today_report: any;
}

function AdminDashboard() {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  const fetchDashboardData = async () => {
    try {
      const response = await fetch('/analytics/dashboard');
      const result = await response.json();
      if (result.success) {
        setDashboardData(result.data);
        setError('');
      } else {
        setError('获取数据失败');
      }
    } catch (err) {
      setError('网络错误');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    
    // 每30秒自动刷新
    const interval = setInterval(fetchDashboardData, 30000);
    setRefreshInterval(interval);

    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
    };
  }, []);

  const handleRefresh = () => {
    setLoading(true);
    fetchDashboardData();
  };

  if (loading) {
    return (
      <div className="admin-dashboard" style={{ padding: '20px', background: '#f5f5f5', minHeight: '100vh' }}>
        <div style={{ textAlign: 'center', marginTop: '100px' }}>
          <div style={{ fontSize: '18px', color: '#666' }}>加载中...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="admin-dashboard" style={{ padding: '20px', background: '#f5f5f5', minHeight: '100vh' }}>
        <div style={{ textAlign: 'center', marginTop: '100px' }}>
          <div style={{ fontSize: '18px', color: '#f56565', marginBottom: '20px' }}>错误: {error}</div>
          <button onClick={handleRefresh} style={{ padding: '10px 20px', background: '#4299e1', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' }}>
            重新加载
          </button>
        </div>
      </div>
    );
  }

  if (!dashboardData) {
    return <div>暂无数据</div>;
  }

  return (
    <div className="admin-dashboard" style={{ padding: '20px', background: '#f5f5f5', minHeight: '100vh' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
          <h1 style={{ fontSize: '2rem', fontWeight: 'bold', color: '#2d3748' }}>用户数据监测台</h1>
          <button 
            onClick={handleRefresh}
            style={{ 
              padding: '10px 20px', 
              background: '#4299e1', 
              color: 'white', 
              border: 'none', 
              borderRadius: '5px', 
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            刷新数据
          </button>
        </div>

        {/* 用户统计卡片 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', marginBottom: '30px' }}>
          <div style={{ background: 'white', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '15px', color: '#2d3748' }}>用户统计</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>总用户数: <strong>{dashboardData.user_stats.total_users}</strong></div>
              <div>今日新增: <strong style={{ color: '#38a169' }}>{dashboardData.user_stats.today_new_users}</strong></div>
              <div>7天活跃: <strong style={{ color: '#3182ce' }}>{dashboardData.user_stats.active_users_7d}</strong></div>
            </div>
          </div>

          <div style={{ background: 'white', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '15px', color: '#2d3748' }}>邀请码状态</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>总邀请码: <strong>{dashboardData.user_stats.total_invite_codes}</strong></div>
              <div>已使用: <strong style={{ color: '#e53e3e' }}>{dashboardData.user_stats.used_invite_codes}</strong></div>
              <div>剩余: <strong style={{ color: '#38a169' }}>{dashboardData.user_stats.unused_invite_codes}</strong></div>
              <div>使用率: <strong>{dashboardData.user_stats.code_usage_rate}</strong></div>
            </div>
          </div>

          <div style={{ background: 'white', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '15px', color: '#2d3748' }}>实时活动</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>当前活跃: <strong style={{ color: '#38a169' }}>{dashboardData.real_time_stats.current_active_users}</strong></div>
              <div>今日操作: <strong>{dashboardData.real_time_stats.today_total_actions}</strong></div>
              <div>近1小时: <strong style={{ color: '#3182ce' }}>{dashboardData.real_time_stats.last_hour_actions}</strong></div>
            </div>
          </div>

          <div style={{ background: 'white', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '15px', color: '#2d3748' }}>搜索统计</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>总搜索: <strong>{dashboardData.search_analytics.total_searches}</strong></div>
              <div>总扩展: <strong>{dashboardData.search_analytics.total_expansions}</strong></div>
              <div>独特搜索词: <strong>{dashboardData.search_analytics.unique_search_keywords}</strong></div>
            </div>
          </div>
        </div>

        {/* 用户行为统计 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px', marginBottom: '30px' }}>
          <div style={{ background: 'white', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '15px', color: '#2d3748' }}>行为类型统计 (7天)</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {Object.entries(dashboardData.action_stats.action_types).map(([action, count]) => (
                <div key={action} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{action}:</span>
                  <strong>{count}</strong>
                </div>
              ))}
            </div>
          </div>

          <div style={{ background: 'white', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '15px', color: '#2d3748' }}>最活跃用户</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {dashboardData.action_stats.most_active_users.slice(0, 8).map(([userId, count], index) => (
                <div key={userId} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                  <span>{userId.substring(0, 8)}...</span>
                  <strong>{count}次</strong>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 热门关键词 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px', marginBottom: '30px' }}>
          <div style={{ background: 'white', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '15px', color: '#2d3748' }}>热门搜索关键词</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {dashboardData.search_analytics.popular_search_keywords.slice(0, 10).map(([keyword, count]) => (
                <div key={keyword} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                  <span style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{keyword}</span>
                  <strong>{count}次</strong>
                </div>
              ))}
            </div>
          </div>

          <div style={{ background: 'white', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '1.2rem', marginBottom: '15px', color: '#2d3748' }}>热门扩展关键词</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {dashboardData.search_analytics.popular_expand_keywords.slice(0, 10).map(([keyword, count]) => (
                <div key={keyword} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                  <span style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{keyword}</span>
                  <strong>{count}次</strong>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 最近活跃用户 */}
        <div style={{ background: 'white', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '15px', color: '#2d3748' }}>最近活跃用户</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '10px' }}>
            {dashboardData.real_time_stats.recent_active_users.map((user, index) => (
              <div key={user.user_id} style={{ 
                background: '#f7fafc', 
                padding: '10px', 
                borderRadius: '4px', 
                fontSize: '0.9rem',
                border: '1px solid #e2e8f0'
              }}>
                <div><strong>用户ID:</strong> {user.user_id.substring(0, 8)}...</div>
                <div><strong>邀请码:</strong> {user.invite_code}</div>
                <div><strong>最后操作:</strong> {user.last_action}</div>
                <div><strong>时间:</strong> {new Date(user.last_action_time).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 最后更新时间 */}
        <div style={{ textAlign: 'center', marginTop: '30px', color: '#718096', fontSize: '0.9rem' }}>
          最后更新: {new Date(dashboardData.real_time_stats.timestamp).toLocaleString()}
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;