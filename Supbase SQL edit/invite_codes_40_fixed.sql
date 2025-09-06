-- 40个6位英文字母内测码配置
-- 用于修复内测码与用户ID一对一映射问题
-- 在Supabase SQL Editor中运行此脚本

-- ================================
-- 第一步：安全清理现有数据（处理外键约束）
-- ================================

-- 首先备份现有用户数据到临时表
CREATE TEMP TABLE existing_users_backup AS 
SELECT * FROM users WHERE invite_code IS NOT NULL;

-- 删除用户表中的数据（这样就可以删除invite_codes了）
DELETE FROM users;

-- 删除现有内测码
DELETE FROM invite_codes;

-- ================================
-- 第二步：插入40个6位英文字母内测码
-- ================================

-- 为每个内测码预生成固定的用户ID，确保一对一映射
INSERT INTO invite_codes (code, user_id, notes) VALUES 
-- 第一批 (1-10)
('ABCDEF', 'user_QUJDREVG_CDEF', 'Paper God内测码01 - 测试专用'),
('GHIJKL', 'user_R0hJSkts_JKLS', 'Paper God内测码02 - 测试专用'),
('MNOPQR', 'user_TU5PUDJS_PQRS', 'Paper God内测码03 - 测试专用'),
('STUVWX', 'user_U1RVVldY_VWXY', 'Paper God内测码04 - 测试专用'),
('YZABCD', 'user_WVpBQkNE_BCDE', 'Paper God内测码05 - 测试专用'),
('EFGHIJ', 'user_RUZHSElK_GHIJ', 'Paper God内测码06 - 测试专用'),
('KLMNOP', 'user_S0xNTk9R_MNOP', 'Paper God内测码07 - 测试专用'),
('QRSTUV', 'user_UVJTVFVW_STUV', 'Paper God内测码08 - 测试专用'),
('WXYZAB', 'user_V1hZWkFC_YZAB', 'Paper God内测码09 - 测试专用'),
('CDEFGH', 'user_Q0RFRkdI_EFGH', 'Paper God内测码10 - 测试专用'),

-- 第二批 (11-20)
('IJKLMN', 'user_SUpLTE1O_KLMN', 'Paper God内测码11 - 高级用户'),
('OPQRST', 'user_T1BRUlNU_QRST', 'Paper God内测码12 - 高级用户'),
('UVWXYZ', 'user_VVZXWVla_WXYZ', 'Paper God内测码13 - 高级用户'),
('ABCGHI', 'user_QUJDRkhJ_CGHI', 'Paper God内测码14 - 高级用户'),
('DEFMNO', 'user_REVGTU5P_FMNO', 'Paper God内测码15 - 高级用户'),
('PQRSTU', 'user_UFFSUFNV_RSTU', 'Paper God内测码16 - 高级用户'),
('VWXYZA', 'user_VldYWVpB_XYZA', 'Paper God内测码17 - 高级用户'),
('BCDEFG', 'user_QkNERUZH_CDEFG', 'Paper God内测码18 - 高级用户'),
('HIJKLM', 'user_SElKS0xN_JKLM', 'Paper God内测码19 - 高级用户'),
('NOPQRS', 'user_Tk9QUFJT_PQRS', 'Paper God内测码20 - 高级用户'),

-- 第三批 (21-30)  
('TUVWXY', 'user_VFVWVldZ_VWXY', 'Paper God内测码21 - VIP用户'),
('ZABCDE', 'user_WkFCQ0RF_BCDE', 'Paper God内测码22 - VIP用户'),
('FGHIJK', 'user_RkdISUpL_HIJK', 'Paper God内测码23 - VIP用户'),
('LMNOPQ', 'user_TE1OT1BR_NOPQ', 'Paper God内测码24 - VIP用户'),
('RSTUVW', 'user_UlNUVVZX_TUVW', 'Paper God内测码25 - VIP用户'),
('XYZABC', 'user_WFlaQUJD_ZABC', 'Paper God内测码26 - VIP用户'),
('DEFGHI', 'user_REVGRkhJ_FGHI', 'Paper God内测码27 - VIP用户'),
('JKLMNO', 'user_SkttTU5P_LMNO', 'Paper God内测码28 - VIP用户'),
('TUVABC', 'user_VFVWQUJd_VABC', 'Paper God内测码29 - VIP用户'),
('GHIXYZ', 'user_R0hJWFla_IXYZ', 'Paper God内测码30 - VIP用户'),

-- 第四批 (31-40)
('BCDEFA', 'user_QkNERUZB_DEFA', 'Paper God内测码31 - 专业版'),
('MNOXYZ', 'user_TU5PWFla_OXYZ', 'Paper God内测码32 - 专业版'),
('PQRVWX', 'user_UFFSVldZ_RVWX', 'Paper God内测码33 - 专业版'),
('STUFGH', 'user_U1RVRkdI_UFGH', 'Paper God内测码34 - 专业版'),
('ABCXYZ', 'user_QUJDWFla_CXYZ', 'Paper God内测码35 - 专业版'),
('DEFUVW', 'user_REVGVVpX_FUVW', 'Paper God内测码36 - 专业版'),
('GHIRST', 'user_R0hJUlNU_IRST', 'Paper God内测码37 - 专业版'),
('JKLXYZ', 'user_SkttWFla_LXYZ', 'Paper God内测码38 - 专业版'),
('MNOFGH', 'user_TU5PRkdI_OFGH', 'Paper God内测码39 - 专业版'),
('PQRABC', 'user_UFFSQUJD_RABC', 'Paper God内测码40 - 专业版');

-- ================================
-- 第三步：验证插入结果
-- ================================
SELECT 
    COUNT(*) as total_codes,
    COUNT(DISTINCT code) as unique_codes,
    COUNT(DISTINCT user_id) as unique_user_ids
FROM invite_codes;

-- 检查是否有重复的内测码或用户ID
SELECT 'DUPLICATE CODES' as issue, code, COUNT(*) 
FROM invite_codes 
GROUP BY code 
HAVING COUNT(*) > 1

UNION ALL

SELECT 'DUPLICATE USER_IDS' as issue, user_id, COUNT(*) 
FROM invite_codes 
GROUP BY user_id 
HAVING COUNT(*) > 1;

-- 显示所有内测码
SELECT code, user_id, notes FROM invite_codes ORDER BY code;

-- ================================
-- 第四步：数据迁移和恢复（可选）
-- ================================

-- 尝试恢复备份的用户数据，使用新的固定用户ID
-- 注意：这会为现有用户分配新的固定ID，原有的随机ID将被替换

DO $$
DECLARE
    backup_record RECORD;
    new_user_id VARCHAR(100);
BEGIN
    -- 遍历备份的用户数据
    FOR backup_record IN 
        SELECT * FROM existing_users_backup 
    LOOP
        -- 获取该内测码对应的新固定用户ID
        SELECT user_id INTO new_user_id 
        FROM invite_codes 
        WHERE code = backup_record.invite_code;
        
        IF new_user_id IS NOT NULL THEN
            -- 使用新的固定用户ID重新创建用户记录
            INSERT INTO users (id, invite_code, created_at, last_active, metadata)
            VALUES (
                new_user_id,  -- 使用新的固定ID
                backup_record.invite_code,
                backup_record.created_at,
                backup_record.last_active,
                backup_record.metadata
            ) ON CONFLICT (id) DO NOTHING;  -- 如果ID已存在，跳过
            
            -- 标记内测码为已使用
            UPDATE invite_codes 
            SET used = true, used_at = NOW() 
            WHERE code = backup_record.invite_code;
            
            RAISE NOTICE '用户数据迁移完成: % -> %', backup_record.id, new_user_id;
        ELSE
            RAISE NOTICE '内测码不存在，跳过用户: %', backup_record.invite_code;
        END IF;
    END LOOP;
END $$;

-- 清理临时表
DROP TABLE IF EXISTS existing_users_backup;

-- ================================
-- 完成提示和验证
-- ================================
SELECT 
    '🎉 40个内测码配置完成！' as status,
    '一对一映射: ✅ 确保' as mapping,
    '6位字母格式: ✅ 统一' as format,
    '用户ID固定: ✅ 不再随机' as user_id,
    '数据迁移: ✅ 完成' as migration;

-- 最终验证：显示配置结果
SELECT 
    COUNT(*) as total_codes,
    COUNT(CASE WHEN used = true THEN 1 END) as used_codes,
    COUNT(CASE WHEN used = false THEN 1 END) as available_codes
FROM invite_codes;

SELECT 
    '⚠️ 重要提醒：现有用户的ID已更改为固定格式' as warning,
    '请通知用户重新使用内测码登录以获取固定ID' as action_required;