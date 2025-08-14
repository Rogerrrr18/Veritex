# 📚 Paper God Beta2 - Supabase 配置完整指南

## 🎯 概述

本指南将帮助您从零开始配置Supabase数据库，实现安全的内测码系统和用户数据隔离。

## 📋 前置准备

- ✅ Supabase账号 (https://supabase.com)
- ✅ 项目创建完成
- ✅ 获取项目URL和API Key

## 🗃️ 数据库架构设计

### 核心表结构
1. **invite_codes** - 内测码管理
2. **users** - 用户账号
3. **user_search_history** - 搜索历史
4. **user_chat_history** - 聊天记录
5. **user_actions** - 行为日志
6. **user_settings** - 用户设置

### 安全特性
- 🔒 **行级安全策略 (RLS)** - 确保数据完全隔离
- 🛡️ **用户上下文验证** - 严格的权限控制
- 🚫 **匿名访问限制** - 仅内测码验证允许匿名

## 🚀 Step-by-Step 配置步骤

### 第一步：登录Supabase控制台

1. 访问 https://supabase.com
2. 登录您的账号
3. 选择您的项目 (例如: jfzchljmfnnsrszabpys)
4. 点击左侧菜单 **"SQL Editor"**

### 第二步：完全重置数据库

在SQL Editor中，新建查询并执行以下脚本：

```sql
-- Supabase完全重置脚本 - 解决策略冲突和数据串联问题
-- 在Supabase SQL Editor中运行

-- 1. 删除所有现有策略
DROP POLICY IF EXISTS "允许匿名查询内测码" ON invite_codes;
DROP POLICY IF EXISTS "允许匿名使用内测码" ON invite_codes;
DROP POLICY IF EXISTS "用户只能查看自己的信息" ON users;
DROP POLICY IF EXISTS "允许创建用户" ON users;
DROP POLICY IF EXISTS "用户只能更新自己的信息" ON users;
DROP POLICY IF EXISTS "允许插入用户行为日志" ON user_actions;
DROP POLICY IF EXISTS "用户只能查看自己的行为日志" ON user_actions;
DROP POLICY IF EXISTS "用户只能查看自己的搜索历史" ON user_search_history;
DROP POLICY IF EXISTS "允许插入用户搜索历史" ON user_search_history;
DROP POLICY IF EXISTS "用户只能更新自己的搜索历史" ON user_search_history;
DROP POLICY IF EXISTS "用户只能删除自己的搜索历史" ON user_search_history;
DROP POLICY IF EXISTS "用户只能查看自己的聊天历史" ON user_chat_history;
DROP POLICY IF EXISTS "允许插入用户聊天历史" ON user_chat_history;
DROP POLICY IF EXISTS "用户只能更新自己的聊天历史" ON user_chat_history;
DROP POLICY IF EXISTS "用户只能删除自己的聊天历史" ON user_chat_history;
DROP POLICY IF EXISTS "用户只能查看自己的设置" ON user_settings;
DROP POLICY IF EXISTS "允许插入用户设置" ON user_settings;
DROP POLICY IF EXISTS "用户只能更新自己的设置" ON user_settings;

-- 删除匿名策略（如果存在）
DROP POLICY IF EXISTS "anonymous_select_invite_codes" ON invite_codes;
DROP POLICY IF EXISTS "anonymous_update_invite_codes" ON invite_codes;
DROP POLICY IF EXISTS "allow_user_insert" ON users;
DROP POLICY IF EXISTS "allow_user_select" ON users;
DROP POLICY IF EXISTS "allow_user_update" ON users;
DROP POLICY IF EXISTS "user_own_actions_only" ON user_actions;
DROP POLICY IF EXISTS "user_own_search_only" ON user_search_history;
DROP POLICY IF EXISTS "user_own_chat_only" ON user_chat_history;
DROP POLICY IF EXISTS "user_own_settings_only" ON user_settings;

-- 2. 删除所有现有表（包含数据）
DROP TABLE IF EXISTS user_settings CASCADE;
DROP TABLE IF EXISTS user_chat_history CASCADE;
DROP TABLE IF EXISTS user_search_history CASCADE;
DROP TABLE IF EXISTS user_actions CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS invite_codes CASCADE;

-- 3. 重新创建所有表
CREATE TABLE invite_codes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    used_at TIMESTAMP WITH TIME ZONE,
    user_id VARCHAR(100),
    notes TEXT
);

CREATE TABLE users (
    id VARCHAR(100) PRIMARY KEY,
    invite_code VARCHAR(50) REFERENCES invite_codes(code),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE user_actions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_search_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id),
    search_id VARCHAR(100) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    original_query TEXT NOT NULL,
    expanded_keywords JSONB NOT NULL,
    papers JSONB NOT NULL,
    max_results INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_chat_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id),
    chat_id VARCHAR(100) UNIQUE NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    title TEXT NOT NULL,
    messages JSONB NOT NULL,
    last_activity TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id VARCHAR(100) REFERENCES users(id) UNIQUE,
    theme VARCHAR(10) DEFAULT 'dark',
    language VARCHAR(10) DEFAULT 'zh',
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. 启用RLS
ALTER TABLE invite_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- 5. 创建严格的RLS策略
-- 内测码策略（允许匿名访问）
CREATE POLICY "anonymous_select_invite_codes" ON invite_codes
    FOR SELECT USING (true);

CREATE POLICY "anonymous_update_invite_codes" ON invite_codes
    FOR UPDATE USING (NOT used);

-- 用户策略（允许创建和查看）
CREATE POLICY "allow_user_insert" ON users
    FOR INSERT WITH CHECK (true);

CREATE POLICY "allow_user_select" ON users
    FOR SELECT USING (true);

CREATE POLICY "allow_user_update" ON users
    FOR UPDATE USING (true);

-- 严格的数据隔离策略 - 关键：使用自定义用户上下文确保数据隔离
CREATE POLICY "user_own_actions_only" ON user_actions
    FOR ALL USING (user_id = current_setting('myapp.current_user_id', true))
    WITH CHECK (user_id = current_setting('myapp.current_user_id', true));

CREATE POLICY "user_own_search_only" ON user_search_history
    FOR ALL USING (user_id = current_setting('myapp.current_user_id', true))
    WITH CHECK (user_id = current_setting('myapp.current_user_id', true));

CREATE POLICY "user_own_chat_only" ON user_chat_history
    FOR ALL USING (user_id = current_setting('myapp.current_user_id', true))
    WITH CHECK (user_id = current_setting('myapp.current_user_id', true));

CREATE POLICY "user_own_settings_only" ON user_settings
    FOR ALL USING (user_id = current_setting('myapp.current_user_id', true))
    WITH CHECK (user_id = current_setting('myapp.current_user_id', true));

-- 6. 插入全新的内测码
INSERT INTO invite_codes (code, notes) VALUES 
('BETA001', '内测码1'),
('BETA002', '内测码2'),
('BETA003', '内测码3'),
('DEV2024', '开发者码'),
('TEST001', '测试码'),
('DEMO001', '演示码');

-- 7. 验证表创建
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```

⚠️ **重要提示**: 这个脚本会删除所有现有数据，请确保在测试环境中执行。

### 第三步：添加用户上下文函数

在SQL Editor中，新建另一个查询并执行：

```sql
-- 创建用户上下文函数支持严格的数据隔离
CREATE OR REPLACE FUNCTION set_current_user_id(user_id TEXT)
RETURNS VOID AS $$
BEGIN
  PERFORM set_config('myapp.current_user_id', user_id, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION get_current_user_id()
RETURNS TEXT AS $$
BEGIN
  RETURN current_setting('myapp.current_user_id', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### 第四步：验证数据库配置

运行验证查询：

```sql
-- 1. 查看创建的表
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- 2. 查看内测码
SELECT code, used, notes FROM invite_codes ORDER BY code;

-- 3. 测试函数
SELECT set_current_user_id('test_user');
SELECT get_current_user_id();
```

**预期结果**:
- 6个表：invite_codes, users, user_actions, user_chat_history, user_search_history, user_settings
- 6个内测码：BETA001, BETA002, BETA003, DEV2024, TEST001, DEMO001
- 函数正常执行

## 🔧 环境变量配置

### 更新 .env 文件

确保前端项目的 `.env` 文件包含正确的配置：

```env
# Supabase配置
VITE_SUPABASE_URL=https://你的项目ID.supabase.co
VITE_SUPABASE_ANON_KEY=你的匿名密钥
```

⚠️ **注意**: 
- 使用 `VITE_` 前缀（Vite项目）
- 不要使用 `NEXT_PUBLIC_` 前缀

## 🧪 测试验证流程

### 第一步：清除浏览器缓存

在浏览器开发者工具控制台中执行：
```javascript
localStorage.clear();
location.reload();
```

### 第二步：测试认证流程

1. **访问应用主页** → 应该被重定向到内测码页面
2. **输入内测码 BETA001** → 显示"验证中..."
3. **验证成功** → 自动跳转到主页，可以正常使用功能
4. **数据隔离测试** → 每个内测码只能看到自己的数据

### 第三步：测试数据隔离

1. 使用 BETA001 登录，进行一些搜索和聊天
2. 清除缓存，使用 BETA002 登录
3. 确认看不到 BETA001 的任何数据

## 🛡️ 安全检查清单

- [ ] RLS策略已启用
- [ ] 每个表都有正确的策略
- [ ] 用户上下文函数正常工作
- [ ] 内测码验证正常
- [ ] 数据完全隔离
- [ ] 匿名用户无法访问敏感数据

## 🔍 故障排除

### 问题：策略已存在错误
**解决方案**: 使用重置脚本中的 `DROP POLICY IF EXISTS` 语句

### 问题：数据串联
**原因**: RLS策略未正确生效
**解决方案**: 确保用户上下文函数已创建并在前端正确调用

### 问题：404错误
**原因**: 表不存在
**解决方案**: 确保所有表都已正确创建

### 问题：权限错误
**解决方案**: 检查API密钥权限和RLS策略配置

## 📊 数据库监控

### 查看用户统计
```sql
SELECT 
  COUNT(*) as total_users,
  COUNT(CASE WHEN last_active > NOW() - INTERVAL '24 hours' THEN 1 END) as active_24h
FROM users;
```

### 查看内测码使用情况
```sql
SELECT 
  COUNT(*) as total_codes,
  COUNT(CASE WHEN used = true THEN 1 END) as used_codes,
  COUNT(CASE WHEN used = false THEN 1 END) as available_codes
FROM invite_codes;
```

### 查看用户活动
```sql
SELECT 
  action,
  COUNT(*) as count
FROM user_actions 
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY action
ORDER BY count DESC;
```

## 🎯 发布前检查

- [ ] 数据库配置完成
- [ ] 内测码已插入
- [ ] 认证流程测试通过
- [ ] 数据隔离验证通过
- [ ] 前端环境变量配置正确
- [ ] 所有功能正常工作

## 📞 技术支持

如遇到问题，请提供以下信息：
1. 错误信息截图
2. 浏览器控制台日志
3. 数据库表查询结果
4. 使用的内测码

---

**🎉 恭喜！您的Paper God Beta2内测系统已配置完成！**