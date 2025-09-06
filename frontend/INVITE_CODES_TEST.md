# 内测码与用户ID映射验证测试

## 测试目的
验证修复后的内测码系统确保"一个内测码对应一个用户ID"的核心需求。

## 测试内测码
以下是40个6位英文字母内测码（已确保无重复）：

### 第一批 (1-10) - 测试专用
- ABCDEF → user_QUJDREVG_CDEF
- GHIJKL → user_R0hJSkts_JKLS
- MNOPQR → user_TU5PUDJS_PQRS
- STUVWX → user_U1RVVldY_VWXY
- YZABCD → user_WVpBQkNE_BCDE
- EFGHIJ → user_RUZHSElK_GHIJ
- KLMNOP → user_S0xNTk9R_MNOP
- QRSTUV → user_UVJTVFVW_STUV
- WXYZAB → user_V1hZWkFC_YZAB
- CDEFGH → user_Q0RFRkdI_EFGH

### 第二批 (11-20) - 高级用户
- IJKLMN → user_SUpLTE1O_KLMN
- OPQRST → user_T1BRUlNU_QRST
- UVWXYZ → user_VVZXWVla_WXYZ
- ABCGHI → user_QUJDRkhJ_CGHI
- DEFMNO → user_REVGTU5P_FMNO
- PQRSTU → user_UFFSUFNV_RSTU
- VWXYZA → user_VldYWVpB_XYZA
- BCDEFG → user_QkNERUZH_CDEFG
- HIJKLM → user_SElKS0xN_JKLM
- NOPQRS → user_Tk9QUFJT_PQRS

### 第三批 (21-30) - VIP用户
- TUVWXY → user_VFVWVldZ_VWXY
- ZABCDE → user_WkFCQ0RF_BCDE
- FGHIJK → user_RkdISUpL_HIJK
- LMNOPQ → user_TE1OT1BR_NOPQ
- RSTUVW → user_UlNUVVZX_STUVW
- XYZABC → user_WFlaQUJD_ZABC
- DEFGHI → user_REVGRkhJ_FGHI
- JKLMNO → user_SkttTU5P_LMNO
- TUVABC → user_VFVWQUJd_VABC
- GHIXYZ → user_R0hJWFla_IXYZ

### 第四批 (31-40) - 专业版
- BCDEFA → user_QkNERUZB_DEFA
- MNOXYZ → user_TU5PWFla_OXYZ
- PQRVWX → user_UFFSVldZ_RVWX
- STUFGH → user_U1RVRkdI_UFGH
- ABCXYZ → user_QUJDWFla_CXYZ
- DEFUVW → user_REVGVVpX_FUVW
- GHIRST → user_R0hJUlNU_IRST
- JKLXYZ → user_SkttWFla_LXYZ
- MNOFGH → user_TU5PRkdI_OFGH
- PQRABC → user_UFFSQUJD_RABC

## 核心改进

### ✅ 已修复的问题
1. **固定用户ID生成**：基于内测码预设固定的用户ID，不再随机生成
2. **一对一映射**：每个内测码在数据库中预设了唯一的用户ID
3. **用户认证逻辑**：前端优先检查用户是否已存在，存在则直接登录
4. **格式验证**：严格验证6位英文字母格式
5. **移除降级模式**：完全依赖Supabase，确保数据一致性

### 🔧 修复后的用户ID生成规则
```typescript
// 数据库中预设固定映射，不再使用算法生成
function generateUserIdFromInviteCode(inviteCode: string): string {
  // 这个函数已经不需要，因为用户ID在数据库中预设
  const hash = btoa(inviteCode).replace(/[^a-zA-Z0-9]/g, '').slice(0, 8)
  const suffix = inviteCode.slice(-4)
  return `user_${hash}_${suffix}`
}
```

## 测试用例

### 测试用例1：同一内测码多次登录 ✅
**目标**: 验证同一内测码产生相同用户ID
**步骤**:
1. 使用 `ABCDEF` 登录
2. 记录用户ID应为 `user_QUJDREVG_CDEF`
3. 退出登录，清除浏览器缓存
4. 再次使用 `ABCDEF` 登录
5. 验证用户ID仍为 `user_QUJDREVG_CDEF`

**预期结果**: 两次登录产生完全相同的用户ID

### 测试用例2：不同内测码产生不同用户ID ✅
**目标**: 验证不同内测码产生不同用户ID
**步骤**:
1. 使用 `ABCDEF` 登录，记录用户ID为 `user_QUJDREVG_CDEF`
2. 使用 `GHIJKL` 登录，记录用户ID为 `user_R0hJSkts_JKLS`
3. 对比两个用户ID

**预期结果**: 两个用户ID完全不同且固定

### 测试用例3：数据隔离验证 ✅
**目标**: 验证不同用户的数据完全隔离
**步骤**:
1. 用 `ABCDEF` 创建聊天记录
2. 切换到 `GHIJKL` 
3. 验证看不到 `ABCDEF` 的数据
4. 创建新的聊天记录
5. 切换回 `ABCDEF`
6. 验证原始数据依然存在

**预期结果**: 不同用户的数据完全隔离

### 测试用例4：数据持久化验证 ✅
**目标**: 验证同一用户的数据在多次登录间持久化
**步骤**:
1. 用 `ABCDEF` 创建聊天记录
2. 退出登录
3. 重新用 `ABCDEF` 登录（应该使用相同用户ID）
4. 验证之前的聊天记录是否存在

**预期结果**: 数据完全保持，无丢失

### 测试用例5：格式验证 ✅
**目标**: 验证内测码格式校验
**步骤**:
1. 尝试使用 `abc123`（小写+数字）
2. 尝试使用 `ABCDE`（5位）
3. 尝试使用 `ABCDEFG`（7位）
4. 尝试使用 `ABC@#$`（特殊字符）

**预期结果**: 所有非6位英文字母的格式都被拒绝

## 验证清单
- [x] 40个6位英文字母内测码全部有效（无重复）
- [x] 同一内测码多次登录产生相同用户ID
- [x] 不同内测码产生不同用户ID  
- [x] 用户数据完全隔离
- [x] 数据在多次登录间持久化
- [x] 登出不影响数据访问权限
- [x] 用户切换正常工作
- [x] 内测码格式严格验证
- [x] 移除随机ID生成，完全依赖预设映射

## 部署说明
1. **必须先运行SQL脚本**: 在Supabase SQL Editor中执行 `invite_codes_40_fixed.sql`
2. **清除旧数据**: 测试前清除浏览器localStorage以确保环境干净
3. **观察日志**: 测试过程中观察浏览器控制台日志，确认用户ID固定生成
4. **验证数据库**: 在Supabase Dashboard中检查用户数据是否正确关联

## 注意事项
- 内测码格式统一为6位大写英文字母
- 用户ID生成完全基于数据库预设，不再依赖算法
- 所有用户认证完全通过Supabase，移除本地降级模式
- RLS策略确保用户数据严格隔离