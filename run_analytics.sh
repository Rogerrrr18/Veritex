#!/bin/bash

# 用户数据监测启动脚本
# 提供快速查看用户数据的命令行工具

echo "=== Veritex 用户数据监测工具 ==="
echo "1. 安装依赖..."

# 检查是否有 supabase 库
python3 -c "import supabase" 2>/dev/null || {
    echo "正在安装 supabase 库..."
    pip3 install supabase
}

echo "2. 运行数据分析..."
python3 user_analytics.py

echo ""
echo "=== 其他可用功能 ==="
echo "- 后台API: python3 -m uvicorn backend:app --reload"
echo "- 前端开发: cd frontend && npm run dev"
echo "- 管理后台: http://localhost:3000/admin"
echo "- API文档: http://localhost:8000/docs"
echo ""
echo "=== 主要API端点 ==="
echo "- GET /analytics/user_stats - 用户统计"
echo "- GET /analytics/user_actions - 用户行为统计"
echo "- GET /analytics/search_analytics - 搜索分析"
echo "- GET /analytics/real_time - 实时统计"
echo "- GET /analytics/dashboard - 仪表板数据"
echo "- GET /analytics/user_timeline/{user_id} - 用户时间线"
echo "- GET /analytics/daily_report - 每日报告"