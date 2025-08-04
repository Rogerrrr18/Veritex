# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered academic literature search system that supports all academic disciplines. It features a **LangGraph-based Agent architecture** with FastAPI backend and React frontend, intelligent keyword expansion using Groq LLM, and multi-source MCP integration.

## Architecture

### Backend (LangGraph Agent Architecture)
- **langchain_agents/**: LangGraph-based intelligent agents
  - `paper_search_agent.py`: Main PaperSearchAgent with async workflow management
  - Supports session-based searches with real-time status tracking
- **langchain_workflows/**: LangGraph state graphs and workflow definitions
  - `paper_search_graph.py`: Complete workflow with nodes and conditional routing
  - `state_schemas.py`: TypedDict state definitions and helper functions
- **langchain_tools/**: LangChain BaseTool wrappers
  - `mcp_google_scholar_tool.py`: Google Scholar MCP integration
  - `mcp_semantic_scholar_tool.py`: Semantic Scholar MCP integration  
  - `keyword_expansion_tool.py`: Groq-powered keyword expansion
  - `multi_search_tool.py`: Multi-source parallel search strategies
  - `result_processing_tool.py`: Advanced result processing and deduplication
- **backend.py**: FastAPI REST API with LangGraph Agent integration
- **Key Features**:
  - **LangGraph workflow engine** with stateful execution
  - **Multi-source MCP integration** (Google Scholar MCP, Semantic Scholar MCP)
  - **Intelligent keyword expansion** using Groq LLM with academic field detection
  - **Advanced search strategies** (fast, balanced, comprehensive, academic)
  - **Real-time progress tracking** and WebSocket support
  - **Automatic retry and quality assessment** mechanisms

### Frontend (React + TypeScript)
- **Vite-based** React application with TypeScript
- **React Router** for navigation between search interface and report view
- **Key Components**:
  - Main search interface with intelligent keyword expansion
  - Editable keyword tags with dynamic validation
  - Report viewer with expandable abstracts and Excel export
- **Dependencies**: react-router-dom

### LangGraph Workflow
1. **Query Analysis**: Analyze user query and detect academic discipline
2. **Keyword Expansion**: Groq LLM expands keywords based on detected field (optional)
3. **Multi-Source Search**: Parallel search across multiple data sources with strategy selection
4. **Result Processing**: Advanced deduplication, relevance scoring, and quality filtering
5. **Quality Assessment**: Evaluate result quality and trigger retry if needed
6. **Final Report**: Generate comprehensive search report with metrics

### Agent API Flow
1. **User initiates search** → POST `/agent/search` with query and preferences
2. **Agent creates session** → Returns session_id for tracking
3. **Real-time monitoring** → WebSocket `/ws/search/{session_id}` for live updates
4. **Retrieve results** → GET `/agent/result/{session_id}` when completed
5. **Legacy compatibility** → Existing `/search_papers` and `/expand_keywords` endpoints supported

## Development Commands

### Backend Setup & Run
```bash
# Install dependencies
pip install -r requirements.txt

# Start backend server (auto-reload enabled)
python -m uvicorn backend:app --reload

# Test LangGraph Agent directly
python langchain_agents/paper_search_agent.py

# Test individual tools
python langchain_tools/keyword_expansion_tool.py
python langchain_tools/multi_search_tool.py

# API documentation
open http://127.0.0.1:8000/docs
```

### Frontend Setup & Run
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint

# Preview production build
npm run preview
```
## Development Guidelines

### LangGraph开发指导原则
- **Agent架构**: 所有新功能都应基于LangGraph Agent架构开发
- **工具封装**: 新工具必须继承LangChain BaseTool并提供适当的类型注解
- **状态管理**: 使用TypedDict定义状态，支持Annotated累积字段
- **异步支持**: 所有工具和节点都应支持异步执行
- **错误处理**: 实现完善的错误处理和重试机制
- **调试支持**: 集成LangSmith用于workflow调试和监控
- **生产监控**: 实时跟踪工作流执行和性能指标

### 通用开发原则
- 前端页面修改必须考虑移动端兼容性，采用响应式设计
- 代码上下文控制:500行以下提供完整代码文件，超过500行提供关键函数代码
- 避免迭代式代码，一次性提供完整修改代码
- 简化代码，仅修复关键问题
- 代码注释全部使用中文
- 每次修改完代码，必须列出修改代码的文件列表（标出：已有/新增），对应代码函数
- 并引导我将项目push到github分支上（可以新创建）

## Testing & Debugging
- Backend logs show keyword expansion results and search progress
- Frontend console shows API request/response details
- Results displayed directly in frontend interface
- Use `/docs` endpoint for interactive API testing

## Important Notes

### LangGraph Architecture Features
- **Stateful Workflows**: Complete search process managed through LangGraph state machines
- **Conditional Routing**: Intelligent decision making with retry and fallback mechanisms  
- **Tool Integration**: Seamless integration of MCP tools, Groq LLM, and custom processors
- **Real-time Tracking**: Live progress updates and session management
- **Advanced Analytics**: Comprehensive search metrics and performance statistics

### API and Integration
- Requires active Groq API key for keyword expansion
- MCP servers automatically managed for Google Scholar and Semantic Scholar
- Rate limiting handled with intelligent delays and retries
- Results returned as structured JSON with rich metadata
- Supports both English and Chinese keyword inputs
- Academic field detection supports 10+ disciplines including computer science, biology, chemistry, physics, medicine, psychology, economics, engineering, social science, and mathematics
- **New Agent APIs**: Session-based search with `/agent/*` endpoints
- **Legacy Support**: Existing `/search_papers` and `/expand_keywords` still functional
- **LangSmith Integration**: Optional monitoring and debugging with environment variable configuration

