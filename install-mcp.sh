#!/bin/bash

# Paper God MCP服务器安装和配置脚本
# 自动安装和配置所需的MCP服务器

echo "🚀 Paper God MCP增强版服务器安装脚本"
echo "======================================"

# 检查Node.js和npm
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 未找到Node.js，请先安装Node.js"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ 错误: 未找到npm，请先安装npm"
    exit 1
fi

echo "✅ Node.js和npm检查通过"

# 安装Smithery CLI（用于管理MCP服务器）
echo "📦 安装Smithery CLI..."
npm install -g @smithery/cli

# 创建MCP配置目录
mkdir -p ~/.mcp-servers
cd ~/.mcp-servers

echo "🔍 安装学术论文搜索MCP服务器..."
# 安装paper-search-mcp服务器
npx -y @smithery/cli install @openags/paper-search-mcp

echo "📊 安装数据分析MCP服务器..."
# 安装pandas数据分析服务器（如果可用）
# npm install -g pandas-mcp-server || echo "⚠️ pandas-mcp-server暂不可用，将使用本地实现"

echo "📈 安装可视化MCP服务器..."
# 安装AntV可视化服务器（如果可用） 
# npm install -g @antv/mcp-server || echo "⚠️ AntV MCP服务器暂不可用，将使用本地实现"

echo "🕸️ 安装知识图谱MCP服务器..."
# 安装Neo4j MCP服务器（需要Neo4j数据库）
# npm install -g neo4j-mcp-server || echo "⚠️ Neo4j MCP服务器暂不可用，需要先安装Neo4j数据库"

# 创建MCP服务器配置文件
echo "⚙️ 创建MCP服务器配置..."

cat > ~/.mcp-servers/config.json << 'EOF'
{
  "mcpServers": {
    "paper-search": {
      "command": "npx",
      "args": ["-y", "@openags/paper-search-mcp"],
      "transport": "stdio",
      "config": {
        "sources": ["arxiv", "pubmed", "semantic_scholar", "google_scholar"],
        "maxConcurrent": 5
      }
    },
    "data-analysis": {
      "command": "python",
      "args": ["-m", "pandas_mcp_server"],
      "transport": "stdio",
      "config": {
        "memoryLimit": "1GB",
        "executionTimeout": 30
      },
      "enabled": false
    },
    "visualization": {
      "command": "node",
      "args": ["antv-mcp-server"],
      "transport": "stdio",
      "config": {
        "chartTypes": ["network", "scatter", "timeline", "bubble"]
      },
      "enabled": false
    },
    "knowledge-graph": {
      "command": "node", 
      "args": ["neo4j-mcp-server"],
      "transport": "stdio",
      "config": {
        "neo4jUri": "bolt://localhost:7687",
        "database": "academic_graph"
      },
      "enabled": false
    }
  }
}
EOF

echo "📝 创建MCP服务器启动脚本..."

# 创建启动脚本
cat > ~/.mcp-servers/start-servers.sh << 'EOF'
#!/bin/bash

echo "🚀 启动Paper God MCP服务器..."

# 启动论文搜索服务器（端口8001）
echo "📚 启动论文搜索服务器..."
npx -y @openags/paper-search-mcp --port 8001 &
PAPER_SEARCH_PID=$!

# 等待服务器启动
sleep 3

echo "✅ MCP服务器启动完成"
echo "论文搜索服务器: http://localhost:8001"
echo ""
echo "进程ID:"
echo "- 论文搜索服务器: $PAPER_SEARCH_PID"
echo ""
echo "要停止服务器，请运行: ~/.mcp-servers/stop-servers.sh"

# 保存进程ID
echo $PAPER_SEARCH_PID > ~/.mcp-servers/pids.txt
EOF

# 创建停止脚本
cat > ~/.mcp-servers/stop-servers.sh << 'EOF'
#!/bin/bash

echo "🛑 停止Paper God MCP服务器..."

if [ -f ~/.mcp-servers/pids.txt ]; then
    while read pid; do
        if kill -0 $pid 2>/dev/null; then
            echo "停止进程: $pid"
            kill $pid
        fi
    done < ~/.mcp-servers/pids.txt
    rm ~/.mcp-servers/pids.txt
    echo "✅ 所有MCP服务器已停止"
else
    echo "⚠️ 未找到运行中的服务器"
fi
EOF

# 设置脚本权限
chmod +x ~/.mcp-servers/start-servers.sh
chmod +x ~/.mcp-servers/stop-servers.sh

echo ""
echo "🎉 MCP服务器安装完成！"
echo ""
echo "📋 接下来的步骤:"
echo "1. 启动MCP服务器:"
echo "   ~/.mcp-servers/start-servers.sh"
echo ""
echo "2. 启动Paper God后端:"
echo "   python -m uvicorn backend:app --reload"
echo ""
echo "3. 启动前端:"
echo "   cd frontend && npm run dev"
echo ""
echo "4. 停止MCP服务器:"
echo "   ~/.mcp-servers/stop-servers.sh"
echo ""
echo "⚠️ 注意："
echo "- 确保已配置.env文件中的GROQ_API_KEY"
echo "- 论文搜索服务器将在端口8001运行"
echo "- 其他MCP服务器需要额外配置（目前已禁用）"
echo ""
echo "🔧 配置文件位置: ~/.mcp-servers/config.json"