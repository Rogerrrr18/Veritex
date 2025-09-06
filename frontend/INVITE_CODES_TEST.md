# 内测码与用户ID映射验证测试

## 测试目的
验证修复后的内测码系统确保"一个内测码对应一个用户ID"的核心需求。

## 测试内测码
以下是40个6位英文字母内测码（已去除重复）：

### 第一批 (1-10)
- ABCDEF
- GHIJKL
- MNOPQR
- STUVWX
- YZABCD
- EFGHIJ
- KLMNOP
- QRSTUV
- WXYZAB
- CDEFGH

### 第二批 (11-20)
- IJKLMN
- OPQRST
- UVWXYZ
- ABCGHI
- DEFMNO
- PQRSTU
- VWXYZA
- BCDEFG
- HIJKLM
- NOPQRS

### 第三批 (21-30)
- TUVWXY
- ZABCDE
- FGHIJK
- LMNOPQ
- RSTUVW
- XYZABC
- DEFGHI
- JKLMNO
- TUVABC
- GHIXYZ

### 第四批 (31-40)
- BCDEFA
- MNOXYZ
- PQRVWX
- STUFGH
- ABCXYZ
- DEFUVW
- GHIRSTU
- JKLXYZ
- MNOFGH
- PQRABC

## 测试用例

### 测试用例1：同一内测码多次登录
**目标**: 验证同一内测码产生相同用户ID
**步骤**:
1. 使用 `ABCDEF` 登录
2. 记录生成的用户ID
3. 退出登录
4. 再次使用 `ABCDEF` 登录
5. 验证用户ID是否相同

**预期结果**: 两次登录产生相同的用户ID

### 测试用例2：不同内测码产生不同用户ID
**目标**: 验证不同内测码产生不同用户ID
**步骤**:
1. 使用 `ABCDEF` 登录，记录用户ID1
2. 使用 `GHIJKL` 登录，记录用户ID2
3. 对比两个用户ID

**预期结果**: 两个用户ID完全不同

### 测试用例3：数据隔离验证
**目标**: 验证不同用户的数据完全隔离
**步骤**:
1. 用 `ABCDEF` 创建一些聊天记录
2. 切换到 `GHIJKL`
3. 验证看不到 `ABCDEF` 的数据
4. 创建新的聊天记录
5. 切换回 `ABCDEF`
6. 验证原始数据依然存在

**预期结果**: 不同用户的数据完全隔离

### 测试用例4：数据持久化验证
**目标**: 验证同一用户的数据在多次登录间持久化
**步骤**:
1. 用 `ABCDEF` 创建聊天记录
2. 退出登录
3. 重新用 `ABCDEF` 登录
4. 验证之前的聊天记录是否存在

**预期结果**: 数据完全保持，无丢失

## 用户ID生成规则
基于内测码的固定用户ID生成：
```typescript
function generateUserIdFromInviteCode(inviteCode: string): string {
  const hash = btoa(inviteCode).replace(/[^a-zA-Z0-9]/g, '').slice(0, 8)
  return `user_${hash}_${inviteCode.slice(-4)}`
}
```

示例：
- `ABCDEF` → `user_QUJDREVG_CDEF`
- `GHIJKL` → `user_R0hJSkts_JKLS`

## 验证清单
- [ ] 同一内测码多次登录产生相同用户ID
- [ ] 不同内测码产生不同用户ID  
- [ ] 用户数据完全隔离
- [ ] 数据在多次登录间持久化
- [ ] 登出不影响数据访问权限
- [ ] 用户切换正常工作
- [ ] 40个6位英文字母内测码全部有效（无重复）

## 注意事项
1. 需要先在Supabase中运行 `supabase_unified_setup.sql` 以创建40个内测码
2. 测试前清除浏览器localStorage以确保干净环境
3. 测试过程中观察浏览器控制台日志
4. 如发现问题，立即记录详细错误信息
5. 内测码格式统一为6位大写英文字母（已确保无重复）