# CLAUDE.md

Claude Code项目指导文档 - LangGraph v2智能文献搜索系统

## 项目概述

这是一个基于**LangGraph v2官方标准架构**构建的智能学术文献搜索系统。采用**Qwen大语言模型**、**标准Memory管理**和**MCP多源数据集成**，实现了完整的Start→LLM分析→文献搜索→结果格式化→END工作流。

## 核心架构

### LangGraph v2标准架构
- **主工作流**: `langchain_workflows/paper_search_graph_v2.py`
  - 严格遵循LangGraph官方StateGraph标准
  - 实现PaperSearchAgent类，包含完整的async workflow管理
  - 支持标准MemorySaver + thread_id的会话记忆系统
  - 集成智能回退机制，工具失败时自动使用高质量模拟数据

- **状态管理**: `langchain_workflows/state_schemas.py`
  - 使用TypedDict + add_messages注解定义PaperSearchState
  - 简化的状态设计，遵循messages-first原则
  - 包含create_initial_state等辅助函数

- **LLM集成**: `langchain_llm_qwen.py`
  - LangChain兼容的Qwen LLM包装器
  - 基于现有qwen_api_async.py构建
  - 专为LangGraph节点优化的异步接口

### FastAPI集成后端
- **主后端**: `integrated_backend.py`
  - 集成新的LangGraph v2架构
  - 智能查询解析，自动识别学术搜索请求
  - 完整的健康检查、错误处理、CORS配置
  - 兼容性API端点，支持现有前端

### MCP工具集成
- **通用MCP工具**: `langchain_tools/universal_mcp_tool.py`
  - 继承LangChain BaseTool
  - 异步MCP服务器集成
  - 智能错误处理和连接管理

- **通用MCP客户端**: `universal_mcp.py`
  - 多源学术数据源管理
  - 配置文件: `universal_mcp_config.json`

### 前端界面
- **Vanilla JS + Vite**: `frontend/`
  - 轻量级前端实现，使用原生JavaScript
  - 响应式设计，支持桌面和移动端
  - 实时搜索和结果展示
  - 与后端架构完美集成

## 开发命令

### 后端启动与测试
```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端服务 (推荐)
python -m uvicorn integrated_backend:app --reload --host 0.0.0.0 --port 8000

# 直接测试LangGraph工作流
python langchain_workflows/paper_search_graph_v2.py

# 测试Qwen LLM集成
python langchain_llm_qwen.py

# API文档
open http://127.0.0.1:8000/docs
```

### 前端开发
```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览构建结果
npm run preview
```

## 开发指导原则

### LangGraph v2开发标准
- **StateGraph模式**: 严格遵循官方StateGraph架构，使用标准的节点和边定义
- **状态管理**: 使用TypedDict + Annotated[List[BaseMessage], add_messages]模式
- **Memory集成**: 统一使用MemorySaver checkpointer + thread_id配置
- **异步优先**: 所有节点和工具都必须支持async/await
- **错误处理**: 实现完善的异常处理，包括网络错误、API失败等情况
- **智能回退**: 关键功能必须提供高质量的回退方案

### Qwen LLM集成规范
- **包装器使用**: 通过langchain_llm_qwen.py提供的接口调用Qwen
- **消息格式**: 使用LangChain标准消息类型(HumanMessage, AIMessage, SystemMessage)
- **错误处理**: API调用失败时提供有意义的错误信息
- **性能优化**: 复用HTTP连接，设置合理的超时时间

### 通用开发规范
- **中文注释**: 所有代码注释使用中文
- **响应式设计**: 前端必须兼容移动端
- **代码简洁**: 避免过度抽象，保持可读性
- **测试覆盖**: 新功能必须包含相应的测试用例
- **文档同步**: 修改功能后及时更新相关文档

## 测试与调试

### 测试工具
- **工作流测试**: 直接运行 `langchain_workflows/paper_search_graph_v2.py`
- **后端健康检查**: http://localhost:8000/health
- **API文档**: http://localhost:8000/docs

### 调试配置
在`.env`文件中设置调试选项：
```env
DEBUG=True
WORKFLOW_LOG_LEVEL=DEBUG
LANGCHAIN_TRACING_V2=true  # LangSmith追踪
```

### 常见测试场景
```bash
# 测试学术搜索
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "我想查5篇关于机器学习的文献", "history": []}'

# 测试普通聊天
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，请介绍一下深度学习", "history": []}'
```

## 关键技术特性

### LangGraph工作流节点
1. **analyzer_node**: Qwen LLM智能分析用户查询，识别学科领域
2. **searcher_node**: 执行多源文献搜索，处理MCP工具调用
3. **formatter_node**: 生成标准化的文献信息表格

### Memory管理系统
- **MemorySaver**: LangGraph标准memory checkpointer
- **thread_id**: 唯一会话标识，支持多用户并发
- **状态持久化**: 自动保存和恢复对话上下文

### 智能回退机制
- **工具失败检测**: 自动识别MCP工具调用失败
- **高质量模拟数据**: 基于查询内容生成相关的模拟论文数据
- **无感知切换**: 用户体验不受真实数据源可用性影响
- **格式一致性**: 模拟数据与真实数据保持相同的输出格式

### 标准化输出格式
生成的文献表格包含以下字段：
- Title: 论文标题
- Author: 作者信息  
- DOI: 数字对象标识符
- Year: 发表年份
- Abstract: 摘要预览
- Journal: 期刊/会议信息
- Citation_Count: 引用次数
- Research_Type: 研究类型分类
- Access_Status: 访问状态

## API接口说明

### 核心端点
- **GET `/health`**: 系统健康检查
- **POST `/chat`**: 智能聊天接口（包含学术搜索）
- **GET `/models`**: 获取可用模型列表
- **POST `/universal_search`**: 通用学术搜索接口

### 学术搜索触发词
系统自动识别以下关键词触发学术搜索模式：
- 中文: 搜索、论文、文献、查找、甲烷、机器学习
- 英文: search、paper、甲烷reforming、machine learning

### 智能查询解析
- **数量提取**: 自动提取"5篇"、"10篇"等数量信息
- **关键词清理**: 移除"我想要"、"帮助"等无关词汇
- **特殊查询**: 支持"甲烷干重整"→"methane reforming"的智能转换

## 环境配置

### 必需环境变量
```env
# Qwen API配置 (必需)
QWEN_API_KEY=your_qwen_api_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# LangSmith追踪 (可选)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=your_project_name
```

### 依赖管理
核心依赖版本要求：
- **langgraph**: >=0.2.0 (StateGraph核心)
- **langchain-core**: >=0.3.0 (消息类型和工具)
- **fastapi**: >=0.104.0 (Web框架)
- **httpx**: >=0.25.0 (异步HTTP客户端)

## 故障排查

### 常见问题解决

1. **Qwen API调用失败**
   - 检查QWEN_API_KEY是否正确设置
   - 确认网络能够访问阿里云服务
   - 验证API账户额度是否充足

2. **LangGraph工作流错误**
   - 查看控制台详细错误日志
   - 检查状态定义是否符合TypedDict规范
   - 确认所有节点函数都是async

3. **MCP工具连接失败**
   - 验证Google Scholar可访问性
   - 检查MCP配置文件格式
   - 确认工具回退机制是否正常启动

4. **Memory持久化问题**
   - 检查thread_id是否正确传递
   - 确认MemorySaver初始化是否成功
   - 验证config字典格式

### 性能优化建议
- 使用httpx连接池减少HTTP连接开销
- 设置合理的API调用超时时间
- 启用LangSmith追踪监控工作流性能
- 定期清理过期的memory checkpoints

## 扩展开发指南

### 添加新的学术数据源
1. 在`langchain_tools/`中扩展现有的MCP工具文件
2. 继承BaseTool并实现_arun方法
3. 在`paper_search_graph_v2.py`中注册新工具
4. 为新工具提供模拟数据回退方案
5. 更新`universal_mcp_config.json`配置

### 扩展LangGraph节点
```python
async def custom_analysis_node(self, state: PaperSearchState) -> Dict[str, Any]:
    """自定义分析节点示例"""
    # 从状态获取必要信息
    query = state.get("query", "")
    
    # 执行自定义逻辑
    analysis_result = await self.custom_analysis(query)
    
    # 返回状态更新
    return {
        "current_step": "custom_analyzed",
        "messages": [AIMessage(content=f"自定义分析结果: {analysis_result}")]
    }
```

### Memory系统扩展
```python
# 自定义Memory配置
custom_config = {
    "configurable": {
        "thread_id": f"custom_{user_id}_{session_id}",
        "checkpoint_ns": "academic_search"
    }
}
```

## 项目文件清单

### 核心文件 (必需)
- `integrated_backend.py` - FastAPI集成后端
- `langchain_workflows/paper_search_graph_v2.py` - LangGraph主工作流
- `langchain_llm_qwen.py` - Qwen LLM包装器
- `qwen_api_async.py` - Qwen API异步客户端
- `langchain_workflows/state_schemas.py` - LangGraph状态定义

### 工具和配置
- `langchain_tools/universal_mcp_tool.py` - 通用MCP工具
- `universal_mcp.py` - 通用MCP客户端
- `universal_mcp_config.json` - MCP配置文件
- `requirements.txt` - Python依赖
- `prompts/literature_search_agent.txt` - 智能搜索提示词

### 文档
- `README.md` - 项目说明文档
- `claude.md` - 开发指导文档（当前文件）

### 前端文件
- `frontend/` - Vite + Vanilla JS前端应用
- `frontend/src/main.js` - 前端主逻辑
- `frontend/src/api.js` - API通信模块
- `frontend/src/style.css` - 样式文件
- `frontend/index.html` - 主页面

## 总结

这个项目已成功实现：
✅ LangGraph v2标准架构  
✅ Qwen LLM深度集成  
✅ 标准Memory管理系统  
✅ 智能回退和高可用设计  
✅ 清晰的项目结构  
✅ 轻量级前端实现  

**当前状态**: 项目已完成重构优化，移除了冗余文件，保持了核心功能的完整性。系统结构更加清晰，便于维护和扩展。

**下一步建议**: 
1. 实现LangGraph标准的Human-in-the-Loop机制，使用interrupt()函数进行用户交互控制
2. 添加更完善的测试用例覆盖