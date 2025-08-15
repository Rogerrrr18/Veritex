# 多租户数据隔离部署指南

## 🎯 概述
Paper God Beta 现已实现完整的逻辑多租户数据隔离机制，确保每个内测用户拥有独立的数据空间。

## 🏗️ 架构特点
- **共享计算与存储**: 所有用户共享相同的应用实例和数据库
- **逻辑多租户隔离**: 通过应用层鉴权 + 访问控制实现数据隔离  
- **行级安全(RLS)**: Supabase数据库级别的数据隔离
- **用户上下文管理**: 动态设置用户身份用于权限控制

## 📁 修改文件列表

### 新增文件
1. **frontend/src/utils/userStorage.ts** - 用户隔离存储工具类
2. **frontend/src/components/DataIsolationTest.tsx** - 数据隔离测试组件  
3. **supabase_rls_functions.sql** - Supabase RLS函数
4. **MULTI_TENANT_DEPLOYMENT_GUIDE.md** - 本部署指南

### 修改文件
1. **frontend/src/hooks/useAuth.ts** - 增强用户切换检测和上下文管理
2. **frontend/src/ChatInterface.tsx** - 用户隔离的聊天数据存储
3. **frontend/src/supabaseClient.ts** - 增强RLS用户上下文设置

## 🚀 部署步骤

### 第一步: Supabase数据库配置

1. 在Supabase SQL Editor中运行重置脚本:
```bash
# 完全重置数据库和RLS策略
@supabase_reset.sql
```

2. 创建RLS支持函数:
```bash
# 创建用户上下文设置函数
@supabase_rls_functions.sql
```

### 第二步: 前端代码部署

1. 安装依赖并构建:
```bash
cd frontend
npm install
npm run build
```

2. 验证环境变量:
```bash
# 确认 .env 文件包含正确的Supabase配置
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

### 第三步: 数据隔离验证

1. 启动开发服务器:
```bash
npm run dev
```

2. 使用不同内测码登录多个账户

3. 在开发者工具中检查localStorage键名格式:
   - 用户隔离数据: `key_name_user_xxx`
   - 全局共享数据: `key_name` (无用户后缀)

## 🔐 数据隔离策略

### localStorage数据分类
```typescript
// 用户隔离数据 (每个用户独立)
USER_DATA_KEYS = {
  CHAT_HISTORY: 'veritex_chat_history',           // 聊天记录
  CURRENT_ANALYSIS: 'veritex_current_analysis',   // 当前关键词分析  
  SEARCH_HISTORY: 'paper_god_search_history',     // 搜索历史
  CHAT_HISTORY_UNIFIED: 'paper_god_chat_history', // 统一聊天历史
  UNIFIED_HISTORY: 'paper_god_unified_history',   // 统一使用历史
  USER_SETTINGS: 'paper_god_user_settings'        // 用户个人设置
}

// 全局共享数据 (所有用户共享)
GLOBAL_DATA_KEYS = {
  THEME: 'veritex_theme',                         // 应用主题
  LANGUAGE: 'veritex_language',                   // 语言设置
  LLM_MODE: 'veritex_llm_mode'                    // LLM模式
}
```

### Supabase数据库隔离
- **user_actions**: 用户行为日志隔离
- **user_search_history**: 搜索历史隔离  
- **user_chat_history**: 聊天历史隔离
- **user_settings**: 用户设置隔离

## 🧪 测试多租户隔离

### 手动测试步骤
1. 使用内测码 BETA001 登录 → 创建一些聊天记录和搜索记录
2. 登出后使用内测码 BETA002 登录 → 确认看不到BETA001的数据
3. 切换回BETA001 → 确认之前的数据依然存在
4. 在浏览器开发者工具查看localStorage → 确认键名包含用户ID

### 自动化测试
添加DataIsolationTest组件到你的应用中进行自动化测试:
```typescript
import DataIsolationTest from './components/DataIsolationTest'

// 在开发环境中添加测试组件
{process.env.NODE_ENV === 'development' && <DataIsolationTest />}
```

## 🔍 监控和调试

### 浏览器控制台日志
查看以下日志来确认多租户功能正常:
```
🔐 设置用户上下文: user_xxx
✅ 保存用户数据: veritex_chat_history_user_xxx  
🔄 检测到用户切换: user_aaa → user_bbb
🗑️ 已清理前用户 user_aaa 的数据
```

### localStorage检查
在浏览器开发者工具 → Application → Local Storage中检查:
- 用户隔离数据键名应包含 `_user_xxx` 后缀
- 全局数据键名不应包含用户后缀
- 用户切换后，前用户的数据应被清理

### Supabase数据库检查
在Supabase Dashboard → Table Editor中验证:
- 每个表的数据都应包含正确的user_id
- 不同用户的数据完全隔离
- RLS策略正确阻止跨用户访问

## ⚠️ 注意事项

### 开发阶段
- 使用提供的测试组件验证隔离功能
- 定期清理测试数据避免混乱
- 确保所有新的数据操作都经过UserStorage类

### 生产部署
- 确认Supabase RLS策略已正确部署
- 监控用户切换时的数据清理日志
- 定期备份Supabase数据库
- 设置错误监控来捕获权限异常

## 🛠️ 故障排除

### 常见问题
1. **用户看到其他用户数据**
   - 检查localStorage键名是否包含用户ID
   - 确认useAuth的用户切换检测是否工作
   - 验证Supabase RLS策略是否正确

2. **数据无法保存**
   - 检查用户是否已登录(userId不为null)
   - 确认Supabase用户上下文是否正确设置
   - 查看浏览器控制台的错误信息

3. **旧数据迁移问题**  
   - 手动触发DataMigration.autoMigrate()
   - 检查旧格式数据是否存在
   - 确认迁移后旧数据已清理

## 📈 性能优化建议

1. **localStorage使用优化**
   - 定期清理过期的用户数据
   - 限制存储的数据量大小
   - 使用压缩存储大型JSON数据

2. **Supabase查询优化**
   - 为常用查询添加数据库索引
   - 使用分页限制返回数据量
   - 缓存用户设置等静态数据

## ✅ 部署验收标准

部署完成后，以下功能必须正常工作:
- [ ] 不同内测码用户完全独立的数据空间
- [ ] 用户切换时自动清理前用户数据  
- [ ] localStorage数据正确的用户隔离格式
- [ ] Supabase数据库RLS正确阻止跨用户访问
- [ ] 全局共享数据(主题、语言)在用户间正确共享
- [ ] 旧数据自动迁移到新隔离格式
- [ ] 用户登出时完整数据清理

---

🎉 **恭喜！** Paper God Beta 现已具备企业级的多租户数据隔离能力，可以安全地进行多用户内测和生产部署。