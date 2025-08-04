#!/bin/bash

# 通用MCP后端启动脚本
# 使用paper-god-py310环境

echo "🚀 启动通用MCP后端服务..."

# 初始化conda
source /opt/anaconda3/etc/profile.d/conda.sh

# 激活paper-god-py310环境
echo "📦 激活paper-god-py310环境..."
conda activate paper-god-py310

# 检查环境
echo "🔍 当前环境信息:"
echo "  Python版本: $(python --version)"
echo "  Python路径: $(which python)"
echo "  工作目录: $(pwd)"

# 检查依赖
echo "🔧 检查关键依赖..."
python -c "
try:
    import fastapi, uvicorn, aiohttp, feedparser
    print('  ✅ 所有依赖已安装')
except ImportError as e:
    print(f'  ❌ 依赖检查失败: {e}')
    exit(1)
"

# 停止可能存在的旧进程
echo "🛑 停止旧的后端进程..."
pkill -f "uvicorn.*universal_backend" || true
pkill -f "uvicorn.*backend.main" || true
sleep 2

# 启动后端服务
echo "🌟 启动通用MCP后端服务..."
echo "  服务地址: http://127.0.0.1:8005"
echo "  API文档: http://127.0.0.1:8005/docs"
echo "  健康检查: http://127.0.0.1:8005/health"
echo "  服务管理: http://127.0.0.1:8005/services"
echo "  通用搜索: http://127.0.0.1:8005/universal_search"
echo ""
echo "🎯 支持的搜索策略: fast, comprehensive, academic"
echo "📚 支持的数据源: arXiv, CrossRef, PubMed, Semantic Scholar"
echo ""
echo "💡 使用 Ctrl+C 停止服务"
echo "----------------------------------------"

# 启动uvicorn服务
python -m uvicorn universal_backend:app \
    --host 127.0.0.1 \
    --port 8005 \
    --reload \
    --reload-dir . \
    --reload-exclude "*.log,*.tmp,__pycache__"