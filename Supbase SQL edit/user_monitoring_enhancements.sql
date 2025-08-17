-- 用户数据监控优化（事件触发 + 聚合视图 + 快速审计）
-- 在 Supabase SQL Editor 中执行

-- 1) 统一用户活跃时间更新触发器（写入 users.last_active）
CREATE OR REPLACE FUNCTION touch_user_last_active()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE users SET last_active = NOW()
  WHERE id = NEW.user_id;
  RETURN NEW;
END;
$$;

-- 对关键写表绑定触发器
DROP TRIGGER IF EXISTS trg_touch_last_active_actions ON user_actions;
CREATE TRIGGER trg_touch_last_active_actions
AFTER INSERT ON user_actions
FOR EACH ROW EXECUTE FUNCTION touch_user_last_active();

DROP TRIGGER IF EXISTS trg_touch_last_active_search ON user_search_history;
CREATE TRIGGER trg_touch_last_active_search
AFTER INSERT ON user_search_history
FOR EACH ROW EXECUTE FUNCTION touch_user_last_active();

DROP TRIGGER IF EXISTS trg_touch_last_active_chat ON user_chat_history;
CREATE TRIGGER trg_touch_last_active_chat
AFTER INSERT ON user_chat_history
FOR EACH ROW EXECUTE FUNCTION touch_user_last_active();

-- 2) 轻量聚合视图：用户使用概览
CREATE OR REPLACE VIEW v_user_usage_summary AS
SELECT 
  u.id AS user_id,
  u.created_at,
  u.last_active,
  COALESCE(a.action_count, 0) AS actions,
  COALESCE(s.search_count, 0) AS searches,
  COALESCE(c.chat_count, 0) AS chats,
  COALESCE(cs.last_chat, NULL) AS last_chat_time,
  COALESCE(ss.last_search, NULL) AS last_search_time
FROM users u
LEFT JOIN (
  SELECT user_id, COUNT(*) AS action_count
  FROM user_actions
  GROUP BY user_id
) a ON a.user_id = u.id
LEFT JOIN (
  SELECT user_id, COUNT(*) AS search_count
  FROM user_search_history
  GROUP BY user_id
) s ON s.user_id = u.id
LEFT JOIN (
  SELECT user_id, COUNT(*) AS chat_count
  FROM user_chat_history
  GROUP BY user_id
) c ON c.user_id = u.id
LEFT JOIN (
  SELECT user_id, MAX(last_activity) AS last_chat
  FROM user_chat_history
  GROUP BY user_id
) cs ON cs.user_id = u.id
LEFT JOIN (
  SELECT user_id, MAX(timestamp) AS last_search
  FROM user_search_history
  GROUP BY user_id
) ss ON ss.user_id = u.id;

-- 3) 每日活跃与事件统计（物化视图，便于看板）
DROP MATERIALIZED VIEW IF EXISTS mv_daily_usage CASCADE;
CREATE MATERIALIZED VIEW mv_daily_usage AS
SELECT 
  day::date,
  (SELECT COUNT(DISTINCT user_id) FROM user_actions WHERE created_at::date = day) AS dau,
  (SELECT COUNT(*) FROM user_actions WHERE created_at::date = day) AS actions,
  (SELECT COUNT(*) FROM user_search_history WHERE created_at::date = day) AS searches,
  (SELECT COUNT(*) FROM user_chat_history WHERE created_at::date = day) AS chats
FROM generate_series(
  (SELECT COALESCE(MIN(created_at), NOW()::date) FROM users)::date,
  NOW()::date,
  interval '1 day'
) day;

-- 刷新函数（可用于 Supabase 任务调度器）
CREATE OR REPLACE FUNCTION refresh_mv_daily_usage()
RETURNS void
LANGUAGE sql
AS $$
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_usage;
$$;

-- 4) 快速审计查询
-- 最近7天活跃
SELECT * FROM mv_daily_usage ORDER BY day DESC LIMIT 7;
-- 用户概览
SELECT * FROM v_user_usage_summary ORDER BY last_active DESC NULLS LAST LIMIT 100;