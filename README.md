# Veritex

**Veritex 是一个面向研究者、学生和知识工作者的 AI-native 文献检索工作台。**

它不是传统关键词搜索框，而是一套“语义理解 -> 查询重写 -> 多源检索 -> 质量排序 -> 对话式解释”的研究基础设施。你可以用自然语言描述一个研究问题，Veritex 会自动拆解学科语境、生成更适合数据库的检索表达，并在 ScholarDock、arXiv、Crossref 等来源中并行检索，最终把结果组织成更适合阅读、比较和继续追问的知识界面。

## 核心能力

- **语义驱动检索**：把模糊问题转成可执行的学术检索策略，而不是只做字符串匹配。
- **多源并行搜索**：聚合 ScholarDock、arXiv、Crossref 等数据源，兼顾覆盖面和响应速度。
- **智能关键词扩展**：按精确术语、核心同义词、相关概念、上下文术语分层扩展查询。
- **质量感知排序**：综合引用数、年份、相关性和元数据完整度筛选结果。
- **对话式研究流**：支持边搜索边追问，让文献检索从一次性搜索变成连续研究过程。
- **OpenAI-compatible 模型接入**：支持通过 `/v1/chat/completions` 兼容接口接入第三方模型服务。
- **工程化交付**：FastAPI 后端、React/Vite 前端、Docker 部署文件和可复用 agent skill 已就绪。

## 近期更新

- 模型层切换为 OpenAI-compatible 优先路径：`ACTIVE_MODEL=openai`。
- 兼容旧 `ARK_*` 环境变量：当 `ARK_BASE_URL` 以 `/v1` 结尾时自动走 OpenAI 适配器。
- LLM 适配器禁用环境代理：`trust_env=False`，避免本机代理污染模型调用。
- `run_dev.sh` 支持从任意目录启动，并允许透传端口：`bash run_dev.sh --port 8012`。
- Vite 代理支持 `VITE_BACKEND_URL`，本地端口冲突时可快速切换后端。
- 新增项目内 skill：`.codex/skills/veritex-model-api/SKILL.md`，供以后 agent 复用模型 API 排障流程。

## 系统要求

- Python 3.9+
- Node.js 16+
- OpenAI-compatible LLM API key
- 推荐: 8GB+ 内存，SSD存储

## 快速开始

### 1. 环境配置

复制环境变量示例：
```bash
cp .env.example .env
```

编辑 `.env` 文件：
```env
ACTIVE_MODEL=openai

# OpenAI-compatible 模型配置
ARK_API_KEY=your_model_api_key
ARK_BASE_URL=https://your-provider.example/v1/
ARK_MODEL_NAME=your-model-name
ARK_TEMPERATURE=0.3
ARK_MAX_TOKENS=2000

# 数据源控制
SCHOLAR_DOCK_ENABLED=true
ARXIV_ENABLED=true
CROSSREF_ENABLED=true
```

### 2. 后端启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端服务
bash run_dev.sh --port 8012
```

验证后端：http://127.0.0.1:8012/docs

验证模型 API：

```bash
python -c 'import asyncio; from llm_interface import get_universal_llm; ns={}; exec("async def main():\n    llm = await get_universal_llm()\n    print(llm.get_model_info())\n    r = await llm.chat_completion([{\"role\": \"user\", \"content\": \"只回复OK\"}], max_tokens=8)\n    print(\"RESULT:\", r)\n    await llm.close()", globals(), ns); asyncio.run(ns["main"]())'
```

成功时应看到 `RESULT: OK` 或等价短回复。

### 3. 前端启动

```bash
cd frontend

# 如果后端不是8000，在 frontend/.env 中设置：
# VITE_BACKEND_URL=http://127.0.0.1:8012

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问应用：http://localhost:5173

## Agent Skill

本仓库内置了一个可复用 skill：

```text
.codex/skills/veritex-model-api/SKILL.md
```

### 拉取并安装 Skill

如果你已经克隆了 Veritex 仓库，可以把 skill 安装到本机 Codex skills 目录：

```bash
git clone https://github.com/Rogerrrr18/Veritex.git
cd Veritex
mkdir -p ~/.codex/skills
rsync -a .codex/skills/veritex-model-api ~/.codex/skills/
```

如果你只想更新这个 skill，进入已有仓库后执行：

```bash
git pull
mkdir -p ~/.codex/skills
rsync -a .codex/skills/veritex-model-api ~/.codex/skills/
```

安装完成后，新开的 Codex/agent 会在可用 skills 中看到：

```text
veritex-model-api
```

你也可以不全局安装，直接让 agent 在当前项目内读取：

```text
请读取 .codex/skills/veritex-model-api/SKILL.md，并使用 veritex-model-api skill 检查模型 API 配置。
```

当以后任何 agent 需要处理以下任务时，应优先读取这个 skill：

- 配置或迁移 Veritex 模型 API
- 判断 OpenAI-compatible endpoint 是否应该走 `OpenAIAdapter`
- 修复 `ACTIVE_MODEL`、`base_url`、`model_name` 不一致
- 移除代理导致的 `socks5h`、`All connection attempts failed` 等问题
- 用项目自己的 `llm_interface` 做端到端模型验证

推荐触发语：`使用 veritex-model-api skill 检查模型 API 配置`。

## 🎯 使用指南

### 搜索论文
1. **输入查询**: 支持中英文关键词或自然语言描述
2. **智能扩展**: 系统自动识别学科并扩展相关术语
3. **多源搜索**: ScholarDock主力搜索70%，其他源分配30%
4. **语义排序**: 基于相似度过滤和排序结果

### 智能对话
1. **学术问答**: 直接提问研究相关问题
2. **文献推荐**: 根据研究方向推荐相关论文
3. **意图识别**: 自动判断是否需要搜索文献

### 结果管理
1. **浏览结果**: 查看标题、作者、摘要、引用数
2. **导出功能**: Excel格式导出搜索结果
3. **排序筛选**: 按相关性、时间、引用数排序

## 🏗️ 项目架构

```
Veritex Beta3/
├── 后端服务
│   ├── backend.py                    # FastAPI主服务
│   ├── multi_source_engine.py        # 多源搜索引擎
│   ├── llm_interface.py              # 统一LLM接口
│   ├── model_config.py               # 模型配置管理
│   └── performance_monitor.py        # 性能监控
├── AI工作流
│   └── langchain_workflows/          # LangGraph智能工作流
│       ├── paper_search_workflow.py  # 论文搜索流程
│       └── state_schemas.py          # 状态模式定义
├── 前端应用
│   └── frontend/                     # React应用
│       ├── src/components/           # 组件库
│       ├── src/contexts/             # 全局状态
│       └── src/utils/                # 工具函数
├── LLM适配器
│   └── adapters/                     # 多模型适配
│       ├── openai_adapter.py
│       ├── claude_adapter.py
│       └── doubao_adapter.py
└── 配置文件
    ├── requirements.txt              # Python依赖
    ├── .env.example                  # 环境变量模板
    └── CLAUDE.md                     # 开发指南
```

## 📊 API接口

### 核心端点

**搜索服务**
- `POST /chat` - 智能对话接口（推荐使用）
- `POST /search_papers` - 传统论文搜索
- `POST /expand_keywords` - 关键词扩展服务

**系统服务**
- `GET /health` - 健康检查和模型状态
- `GET /performance` - 性能统计
- `GET /models` - 可用LLM模型

**请求示例**:
```bash
# 智能对话搜索
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "机器学习在医学影像诊断中的最新进展", "max_papers": 20}'

# 传统搜索
curl -X POST "http://127.0.0.1:8000/search_papers" \
  -H "Content-Type: application/json" \
  -d '{"query": "deep learning medical imaging", "max_results": 30}'
```

完整API文档：http://127.0.0.1:8000/docs

## 🔧 开发命令

### 后端开发
```bash
# 启动开发服务器
python -m uvicorn backend:app --reload

# 停止后端服务
lsof -ti:8000 | xargs kill -9

# 代码格式化
black . && isort .

# 运行测试（需要时）
python -m pytest
```

### 前端开发
```bash
cd frontend

# 开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint

# 类型检查
npm run type-check
```

## 🔍 性能特性

### 智能搜索优化
- **智能源过滤**: 分层过滤策略，用户选择源为主（75%+），高质量补偿结果适度保留（25%内）
- **质量评估**: 综合评分系统自动筛选最优补偿搜索结果
  - 引用数评分 (40%权重): 基于对数标准化，避免极值主导
  - 年份评分 (30%权重): 较新论文得分更高
  - 相关性评分 (30%权重): 基于标题、摘要完整性和DOI
- **并行搜索**: 多数据源同时查询，减少总体延迟
- **智能补偿**: 自动启动备用数据源，确保搜索覆盖面
- **错误恢复**: 智能重试和降级机制

### 系统优化
- **缓存机制**: 关键词扩展结果复用，减少重复LLM调用
- **连接池**: 优化HTTP连接管理，提升网络效率  
- **异步架构**: 支持高并发处理
- **性能监控**: 实时统计响应时间和成功率
- **透明记录**: 详细的源贡献统计和过滤过程日志

## 🐛 故障排除

### 常见问题
1. **arXiv连接失败**: 确保使用HTTPS协议（已修复）
2. **API密钥错误**: 检查`.env`文件配置
3. **端口冲突**: 使用`lsof -i :8000`检查端口
4. **语义搜索无效果**: 调整`SEMANTIC_THRESHOLD`参数

### 网络问题
- **Google Scholar限制**: 系统自动切换到其他数据源
- **连接超时**: 增加超时时间或检查网络连接
- **代理设置**: 配置HTTP_PROXY环境变量

## 📈 版本历史

### v3.1 (2025-09-23) - 当前版本
- ✅ **重大突破**: 智能源过滤机制重构，实现分层过滤策略
- ✅ **质量评估**: 综合评分系统（引用数+年份+相关性）筛选补偿结果
- ✅ **增强日志**: 详细的源贡献统计和构成比例展示
- ✅ **前端优化**: 报告页面citations升降序排序功能
- ✅ **项目清理**: 删除临时测试脚本，优化代码结构
- ✅ **智能补偿**: 保留高质量补偿搜索结果，提升搜索覆盖面

### v3.0 (2025-08-26)
- ✅ 修复arXiv HTTPS连接问题
- ✅ 优化语义搜索过滤阈值（0.3→0.6）
- ✅ 增强网络错误诊断和处理
- ✅ 清理项目结构，删除测试文件
- ✅ 更新文档和开发指南

### v2.x (2025-01-18)
- 搜索篇数分配优化
- ScholarDock引擎429错误处理
- LangGraph智能工作流集成
- 性能监控系统

## 🤝 贡献指南

1. Fork项目仓库
2. 创建特性分支: `git checkout -b feature/新功能`
3. 提交更改: `git commit -m '添加新功能'`
4. 推送分支: `git push origin feature/新功能`
5. 创建Pull Request

### 代码规范
- Python: 使用black + isort格式化
- TypeScript: 遵循ESLint规则
- 提交信息: 使用中文简洁描述

## 📄 许可证

本项目采用MIT许可证 - 详见[LICENSE](LICENSE)文件

## 🙏 致谢

**核心技术**
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能Python Web框架
- [LangGraph](https://langchain-ai.github.io/langgraph/) - AI工作流编排
- [React](https://reactjs.org/) + [TypeScript](https://www.typescriptlang.org/) - 现代前端框架

**数据源**
- [Google Scholar](https://scholar.google.com/) - 学术搜索
- [Semantic Scholar](https://www.semanticscholar.org/) - 语义学术数据
- [arXiv](https://arxiv.org/) - 预印本论文
- [PubMed](https://pubmed.ncbi.nlm.nih.gov/) - 生物医学文献

**AI服务**
- [OpenAI](https://openai.com/) - GPT模型
- [Anthropic](https://anthropic.com/) - Claude模型  
- [Groq](https://groq.com/) - 高速推理

---

💡 **提示**: 遇到问题请先查看[开发指南](CLAUDE.md)或提交Issue获得帮助。
