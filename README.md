# Paper God Beta2 - 智能学术文献搜索系统

一个基于AI的多源学术文献搜索引擎，支持智能关键词扩展、多数据源并行搜索和作者网络分析。

**最新更新 (2025-01-18)**: 优化了搜索篇数分配逻辑，修复了scholarly库429错误处理，提升了搜索结果准确性。

## 🚀 核心特性

- **智能关键词扩展**: 基于LLM的学科自适应关键词扩展，支持10+学科领域
- **优化搜索分配**: scholarly主力搜索源获得70%配额，确保搜索结果数量符合用户期望
- **多源并行搜索**: 整合arXiv、Google Scholar、Semantic Scholar等高质量数据源
- **稳定429处理**: 参考Paper-god-beta2项目优化scholarly库调用，降低访问限制
- **智能对话系统**: 集成LangGraph工作流，支持学术问答和文献推荐
- **响应式前端**: React + TypeScript构建的现代化界面，支持移动端
- **高性能后端**: FastAPI异步架构，支持并发搜索和性能监控

## 📋 系统要求

- Python 3.9+
- Node.js 16+
- LLM API密钥 (OpenAI/Anthropic/Groq)
- 推荐: 8GB+ 内存，SSD存储

## 🔧 快速开始

### 1. 环境配置

在项目根目录创建 `.env` 文件：
```env
# LLM API配置 (选择其一)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key  
GROQ_API_KEY=your_groq_key

# 数据源控制
GOOGLE_SCHOLAR_ENABLED=true
SEMANTIC_SCHOLAR_ENABLED=true
ARXIV_ENABLED=true

# 可选API密钥
PUBMED_API_KEY=disabled
CROSSREF_ENABLED=false
```

API密钥获取地址：
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/
- Groq: https://console.groq.com/

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

### 搜索论文
1. 输入关键词，支持中英文
2. 设置搜索参数（篇数、年份范围等）
3. 系统自动扩展关键词并搜索多个数据源
4. scholarly主力搜索获得70%配额，确保结果数量

### 智能对话
1. 直接提问学术问题
2. 系统智能判断是否需要搜索文献
3. 提供基于文献的专业回答

### 结果管理
1. 浏览搜索结果，展开查看摘要详情
2. 使用Excel导出功能保存搜索结果
3. 按相关性、引用数等排序

## 🏗️ 项目架构

```
Paper God Beta2/
├── 核心后端
│   ├── backend.py                    # FastAPI主服务
│   ├── multi_source_engine.py        # 优化的多源搜索引擎
│   ├── llm_interface.py              # 统一LLM接口
│   ├── performance_monitor.py        # 性能监控
│   └── prompt_utils.py               # 提示词管理
├── 智能工作流
│   ├── langchain_workflows/          # LangGraph智能工作流
│   │   ├── paper_search_workflow.py  # 论文搜索工作流
│   │   └── chat_workflow.py          # 对话工作流
├── 前端应用
│   └── frontend/                     # React + TypeScript应用
├── 测试文件
│   ├── test_search_quota.py          # 搜索配额测试
│   └── test_large_search.py          # 大量搜索测试
└── 配置文件
    ├── requirements.txt              # 最新Python依赖
    ├── CLAUDE.md                     # 开发指南
    └── .env.example                  # 环境变量示例
```

## 📊 API接口

### 主要端点

**搜索服务**
- `POST /chat` - 智能对话接口（推荐）
- `POST /search_papers` - 论文搜索（支持预扩展关键词优化）
- `POST /expand_keywords` - 独立关键词扩展

**系统服务**
- `GET /health` - 健康检查和模型状态
- `GET /performance` - 性能统计信息
- `GET /models` - 可用LLM模型列表

**分析服务**
- `POST /analytics/register` - 用户注册统计
- `POST /analytics/log_action` - 行为日志记录

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

**搜索优化**
- scholarly主力搜索获得70%配额，显著提升结果数量
- 优化的429错误处理，降低Google Scholar访问限制
- 智能配额分配：30篇搜索 = scholarly 21篇 + 其他源9篇

**系统优化**
- 快速意图预筛选，避免不必要的LLM调用
- 预扩展关键词复用，减少重复分析
- 内置性能监控，实时跟踪响应时间和成功率
- 支持并发搜索，可同时处理多个查询请求

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📝 许可证

本项目采用MIT许可证 - 详见 [LICENSE](LICENSE) 文件

## 🔄 版本历史

### v3.0 (2025-01-18)
- ✅ 修复搜索篇数分配问题：scholarly获得70%配额
- ✅ 优化scholarly库429错误处理
- ✅ 集成LangGraph智能工作流
- ✅ 添加性能监控和统计
- ✅ 支持多LLM模型切换

### v2.0 (2024)
- 多源搜索引擎
- 智能关键词扩展
- React前端界面

## 🙏 致谢

- [Semantic Scholar API](https://www.semanticscholar.org/product/api)
- [arXiv API](https://arxiv.org/help/api)
- [Google Scholar Scholarly](https://scholarly.readthedocs.io/)
- [OpenAI](https://openai.com/) / [Anthropic](https://anthropic.com/) / [Groq](https://groq.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [React](https://reactjs.org/)