# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered academic literature search system that supports all academic disciplines. It consists of a FastAPI backend and React frontend with intelligent keyword expansion using Groq LLM and Google Scholar integration.

## Architecture

### Backend (FastAPI)
- **main.py**: Core literature collection engine with `GroqKeywordExpander`, `QueryBuilder`, and `LiteratureCollector` classes
- **backend.py**: FastAPI REST API that wraps main.py functionality
- **Key Features**:
  - Multi-discipline keyword expansion using Groq LLM
  - Automatic academic field detection (10+ disciplines supported)
  - Two-phase search strategy (precise AND queries, then broader OR queries)
  - Direct result display without file generation

### Frontend (React + TypeScript)
- **Vite-based** React application with TypeScript
- **React Router** for navigation between search interface and report view
- **Key Components**:
  - Main search interface with intelligent keyword expansion
  - Editable keyword tags with dynamic validation
  - Report viewer with expandable abstracts and Excel export
- **Dependencies**: react-router-dom

### Data Flow
1. User enters keywords → Frontend sends to `/expand_keywords`
2. Groq LLM expands keywords based on detected academic discipline
3. User initiates search → Frontend sends to `/search_papers`
4. Backend performs two-phase Google Scholar search with relevance filtering
5. Results returned directly to frontend
6. Frontend displays interactive results

## Development Commands

### Backend Setup & Run
```bash
# Install dependencies
pip install -r requirements.txt

# Start backend server (auto-reload enabled)
python -m uvicorn backend:app --reload

# Run standalone CLI version
python main.py

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

### 开发指导原则
- 前端页面修改必须考虑移动端兼容性，采用响应式设计
- 代码上下文控制:500行以下提供完整代码文件，超过500行提供关键函数代码
- 避免迭代式代码，一次性提供完整修改代码
- 简化代码，仅修复关键问题
- 代码注释全部使用中文
- 每次修改完代码，必须列出修改代码的文件列表（标出：已有/新增），对应代码函数
-并引导我将项目push到github分支上（可以新创建）

## Testing & Debugging
- Backend logs show keyword expansion results and search progress
- Frontend console shows API request/response details
- Results displayed directly in frontend interface
- Use `/docs` endpoint for interactive API testing

## Important Notes
- Requires active Groq API key for keyword expansion
- Google Scholar rate limiting handled with random delays (1-3 seconds)
- Results are returned as JSON and displayed in the frontend
- Supports both English and Chinese keyword inputs
- Academic field detection supports 10+ disciplines including computer science, biology, chemistry, physics, medicine, psychology, economics, engineering, social science, and mathematics

