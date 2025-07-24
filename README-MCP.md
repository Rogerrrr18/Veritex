# Paper God MCP增强版 - 快速启动指南

## 🎯 项目概述

Paper God 已经从传统的学术文献搜索工具全面升级为基于MCP (Model Context Protocol) 的智能研究助手。新版本集成了多个MCP服务器，提供多源搜索、数据分析和可视化功能。

## 🏗️ 新架构特点

### ✅ 已完成的重构
- **MCP客户端层** (`mcp_client.py`) - 统一管理所有MCP服务器
- **重构后端** (`backend.py`) - 新增MCP增强API端点
- **简化核心** (`main.py`) - 保留Groq关键词扩展，移除过时组件
- **更新前端** - 支持传统模式和MCP增强模式切换
- **依赖更新** - 集成MCP相关依赖和安装脚本

### 🚀 核心功能

1. **传统模式**: Groq关键词扩展 + Scholarly搜索 (向后兼容)
2. **MCP增强模式**: 多源搜索 + 数据分析 + 可视化 (新功能)
3. **MCP服务器集成**: 
   - 论文搜索: openags/paper-search-mcp
   - 数据分析: pandas-mcp-server (计划中)
   - 可视化: antv-mcp-server (计划中)
   - 知识图谱: neo4j-mcp-server (计划中)

## 🛠️ 安装和启动

### 步骤1: 安装Python依赖
```bash
pip install -r requirements.txt
```

### 步骤2: 配置环境变量
```bash
# 复制并配置.env文件
cp .env.example .env

# 编辑.env文件，配置以下变量:
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=mixtral-8x7b-32768
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

### 步骤3: 安装MCP服务器 (可选)
```bash
# 运行MCP安装脚本
./install-mcp.sh

# 启动MCP服务器
~/.mcp-servers/start-servers.sh
```

### 步骤4: 启动后端服务
```bash
python -m uvicorn backend:app --reload
```

### 步骤5: 启动前端 (新终端)
```bash
cd frontend
npm install
npm run dev
```

## 🧪 测试功能

### 1. 测试传统模式
- 访问 http://localhost:5173
- 选择"传统搜索"模式
- 输入搜索关键词，验证Groq扩展和Scholarly搜索

### 2. 测试MCP增强模式
- 选择"MCP增强"模式
- 启用数据源选择和分析选项
- 验证多源搜索结果

### 3. 测试API端点
```bash
# 测试关键词扩展
curl -X POST http://localhost:8000/expand_keywords \
  -H "Content-Type: application/json" \
  -d '{"keywords": "machine learning", "user_id": "test_user"}'

# 测试传统搜索
curl -X POST http://localhost:8000/search_papers \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["machine learning", "neural networks"], "max_results": 10, "user_id": "test_user"}'

# 测试MCP健康检查
curl http://localhost:8000/mcp/health
```

## 🔄 降级策略

系统设计了完善的降级机制：

1. **MCP不可用时**: 自动降级到Scholarly搜索
2. **Groq API不可用时**: 跳过关键词扩展，直接搜索
3. **各服务独立**: 单个MCP服务器故障不影响其他功能

## 📁 主要文件说明

```
Paper-god-beta2/
├── mcp_client.py          # MCP客户端核心 (新增)
├── backend.py             # FastAPI后端 (重构)
├── main.py                # 核心逻辑 (简化)
├── requirements.txt       # Python依赖 (更新)
├── install-mcp.sh         # MCP安装脚本 (新增)
├── frontend/src/App.tsx   # React前端 (更新)
└── README-MCP.md          # 本文档 (新增)
```

## 🚨 故障排除

### MCP服务器连接失败
```bash
# 检查MCP服务器状态
curl http://localhost:8001/health

# 重启MCP服务器
~/.mcp-servers/stop-servers.sh
~/.mcp-servers/start-servers.sh
```

### 传统模式不工作
- 检查GROQ_API_KEY配置
- 验证scholarly库安装
- 查看后端日志

### 前端显示错误
- 检查用户登录状态
- 验证后端API连接
- 查看浏览器控制台

## 🔧 开发者模式

### 仅启动后端进行测试
```bash
# 测试核心搜索功能
python main.py "machine learning"

# 启动后端API
python -m uvicorn backend:app --reload --port 8000
```

### 调试MCP连接
```python
# 在Python中测试MCP客户端
from mcp_client import get_mcp_client
import asyncio

async def test_mcp():
    client = await get_mcp_client()
    health = await client.health_check()
    print("MCP健康状态:", health)

asyncio.run(test_mcp())
```

## 📈 性能监控

- 后端日志: 查看uvicorn输出
- MCP服务器状态: `GET /mcp/health`
- 用户分析: `GET /analytics/dashboard`

## 🔮 未来扩展

1. **更多MCP服务器**: 集成更多专业学术数据库
2. **高级可视化**: 引用网络图、时间线分析
3. **AI增强**: 论文摘要生成、研究建议
4. **协作功能**: 团队研究管理、共享报告

---

**注意**: 这是一个重大架构升级。如果遇到问题，可以暂时禁用MCP功能，系统会自动降级到传统模式。