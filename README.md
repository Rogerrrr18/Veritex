# Paper God Beta2 - 智能学术文献搜索系统

一个基于AI的多源学术文献搜索引擎，支持智能关键词扩展、多数据源并行搜索和作者网络分析。

## 🚀 核心特性

- **智能关键词扩展**: 基于Groq LLM的学科自适应关键词扩展
- **多源并行搜索**: 整合arXiv、Google Scholar、Crossref、PubMed等数据源
- **作者网络分析**: 深度作者关系和合作网络分析
- **响应式前端**: React + TypeScript构建的现代化界面
- **高性能后端**: FastAPI异步架构，支持并发搜索

## 📋 系统要求

- Python 3.9+
- Node.js 16+
- Groq API密钥

## 🔧 快速开始

### 1. 环境配置

在项目根目录创建 `.env` 文件：
```env
# Groq API Key (必需)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=gemma2-9b-it

# 可选API密钥
PUBMED_API_KEY=disabled
```

获取Groq API密钥：https://console.groq.com/

### 2. 后端启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端服务
python -m uvicorn backend:app --reload
```

验证后端：访问 http://127.0.0.1:8000/docs

### 3. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问应用：http://localhost:5173

## 🎯 使用方式

1. **搜索论文**: 输入关键词，系统自动扩展并搜索多个数据源
2. **查看结果**: 浏览搜索结果，点击展开查看摘要详情
3. **导出数据**: 使用Excel导出功能保存搜索结果
4. **作者分析**: 点击作者姓名查看详细档案和合作网络

## 🏗️ 项目架构

```
Paper God Beta2/
├── 后端模块
│   ├── backend.py              # FastAPI主服务
│   ├── main.py                 # 核心搜索引擎
│   ├── multi_source_engine.py  # 多源数据获取
│   ├── enhanced_keyword_expander.py  # 关键词扩展
│   ├── discipline_detector.py  # 学科检测
│   ├── author_analyzer.py      # 作者分析
│   ├── enhanced_semantic_search.py  # 语义搜索
│   ├── performance_optimizer.py     # 性能优化
│   └── search_utils.py         # 搜索工具
├── 前端应用
│   └── frontend/               # React + TypeScript应用
└── 配置文件
    ├── requirements.txt        # Python依赖
    └── CLAUDE.md              # 开发指南
```

## 📊 API接口

### 主要端点

- `GET /health` - 健康检查
- `POST /expand_keywords` - 关键词扩展
- `POST /search_papers` - 论文搜索
- `GET /author/search` - 作者搜索
- `GET /author/{author_id}` - 作者详情
- `GET /collaboration_network/{author_id}` - 合作网络

详细API文档：http://127.0.0.1:8000/docs

## 🔧 开发命令

### 后端开发
```bash
# 运行测试
pytest

# 代码格式化
black .
isort .

# 启动开发服务器
python -m uvicorn backend:app --reload
```

# 停止后端服务（如需）
lsof -ti:8000 | xargs kill -9

### 前端开发
```bash
cd frontend

# 开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint
```

## 🐛 故障排除

### 常见问题

1. **端口被占用**: 使用 `lsof -i :8000` 检查端口使用情况
2. **API密钥错误**: 确认 `.env` 文件中的GROQ_API_KEY正确
3. **代理连接失败**: 确保后端服务已启动且运行在8000端口
4. **依赖安装失败**: 建议使用Python虚拟环境

### 性能优化

- 系统内置缓存机制，重复查询会自动使用缓存结果
- 支持并发搜索，可同时处理多个查询请求
- 智能查询优化，自动调整搜索策略

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📝 许可证

本项目采用MIT许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [Semantic Scholar API](https://www.semanticscholar.org/product/api)
- [arXiv API](https://arxiv.org/help/api)
- [Groq](https://groq.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://reactjs.org/)