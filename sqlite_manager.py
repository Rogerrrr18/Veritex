"""
SQLite本地数据库管理器
专为生产环境设计，支持用户隔离和数据持久化
替代Supabase，提供成本效益的数据存储方案
"""

import aiosqlite
import asyncio
import json
import logging
import uuid
import threading
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import asdict
from contextlib import asynccontextmanager

# 导入数据模型
from models.conversation import Conversation, ChatMessage, ConversationMetadata

logger = logging.getLogger(__name__)

class SQLiteManager:
    """SQLite数据库管理器 - 生产级用户数据持久化"""
    
    def __init__(self, db_path: str = "data/veritex.db"):
        """初始化SQLite管理器"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._initialized = False
        # 🔧 修复：移除连接池，避免线程冲突
        self._db_lock = threading.Lock()
        
        logger.info(f"SQLite管理器初始化: {self.db_path}")
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接的异步上下文管理器 - 每次创建新连接避免线程冲突"""
        if not self._initialized:
            await self.initialize()
        
        conn = None
        try:
            # 🔧 修复：每次创建新连接，避免threads can only be started once错误
            conn = await aiosqlite.connect(self.db_path)
            # 启用外键约束
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        except Exception as e:
            logger.error(f"数据库连接错误: {e}")
            if conn:
                await conn.close()
            raise
        finally:
            if conn:
                await conn.close()
    
    async def initialize(self):
        """初始化数据库表结构"""
        if self._initialized:
            return
            
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 启用外键约束
                await db.execute("PRAGMA foreign_keys = ON")
                
                # 创建用户表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        invite_code TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP,
                        metadata TEXT DEFAULT '{}'
                    )
                """)
                
                # 创建邀请码表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS invite_codes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT UNIQUE NOT NULL,
                        description TEXT,
                        used BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        used_at TIMESTAMP,
                        user_id TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                """)
                
                # 创建对话表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        conversation_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        title TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        message_count INTEGER DEFAULT 0,
                        tags TEXT DEFAULT '[]',
                        is_archived BOOLEAN DEFAULT FALSE,
                        metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)
                
                # 创建消息表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_messages (
                        id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        sequence_number INTEGER NOT NULL,
                        message_metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)
                
                # 创建搜索历史表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_search_history (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        search_id TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        original_query TEXT NOT NULL,
                        expanded_keywords TEXT DEFAULT '[]',
                        papers TEXT DEFAULT '[]',
                        max_results INTEGER DEFAULT 20,
                        domain TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)
                
                # 创建聊天历史表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_chat_history (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        chat_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        title TEXT NOT NULL,
                        messages TEXT NOT NULL,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        message_count INTEGER DEFAULT 0,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)
                
                # 创建用户设置表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL UNIQUE,
                        theme TEXT DEFAULT 'dark',
                        language TEXT DEFAULT 'zh',
                        settings TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)
                
                # 创建用户行为日志表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_actions (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        payload TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)
                
                # 创建索引以提升查询性能
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_conversations_last_activity ON conversations (last_activity)",
                    "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON conversation_messages (conversation_id)",
                    "CREATE INDEX IF NOT EXISTS idx_messages_user_id ON conversation_messages (user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_search_history_user_id ON user_search_history (user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_search_history_timestamp ON user_search_history (timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON user_chat_history (user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions (user_id)",
                ]
                
                for index_sql in indexes:
                    await db.execute(index_sql)
                
                await db.commit()
                
                self._initialized = True
                logger.info("SQLite数据库表结构初始化完成")
                
        except Exception as e:
            logger.error(f"SQLite数据库初始化失败: {e}")
            raise
    
    async def get_connection(self) -> aiosqlite.Connection:
        """获取数据库连接"""
        if not self._initialized:
            await self.initialize()
        return await aiosqlite.connect(self.db_path)
    
    # ===== 用户管理 =====
    
    async def create_user(self, user_id: str, invite_code: str) -> bool:
        """创建新用户"""
        try:
            async with self.get_connection() as db:
                await db.execute(
                    "INSERT INTO users (id, invite_code, created_at, last_active) VALUES (?, ?, ?, ?)",
                    (user_id, invite_code, datetime.now().isoformat(), datetime.now().isoformat())
                )
                await db.commit()
                logger.info(f"用户创建成功: {user_id}")
                return True
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            return False
    
    async def update_user_activity(self, user_id: str) -> bool:
        """更新用户最后活跃时间"""
        try:
            async with self.get_connection() as db:
                await db.execute(
                    "UPDATE users SET last_active = ? WHERE id = ?",
                    (datetime.now().isoformat(), user_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"更新用户活跃时间失败: {e}")
            return False
    
    async def validate_invite_code(self, code: str) -> Optional[Dict]:
        """验证邀请码"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    "SELECT * FROM invite_codes WHERE code = ? AND used = FALSE",
                    (code,)
                )
                result = await cursor.fetchone()
                if result:
                    return {
                        'id': result[0],
                        'code': result[1],
                        'description': result[2],
                        'used': result[3],
                        'created_at': result[4]
                    }
                return None
        except Exception as e:
            logger.error(f"验证邀请码失败: {e}")
            return None
    
    async def mark_invite_code_used(self, code: str, user_id: str) -> bool:
        """标记邀请码为已使用"""
        try:
            async with self.get_connection() as db:
                await db.execute(
                    "UPDATE invite_codes SET used = TRUE, used_at = ?, user_id = ? WHERE code = ?",
                    (datetime.now().isoformat(), user_id, code)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"标记邀请码使用失败: {e}")
            return False
    
    # ===== 对话管理 =====
    
    async def save_conversation(self, conversation: Conversation, user_id: str) -> bool:
        """保存对话到数据库"""
        try:
            async with self.get_connection() as db:
                # 保存或更新对话基本信息
                await db.execute("""
                    INSERT OR REPLACE INTO conversations 
                    (conversation_id, user_id, title, created_at, updated_at, last_activity, 
                     message_count, tags, is_archived, metadata) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conversation.conversation_id,
                    user_id,
                    conversation.metadata.title,
                    conversation.metadata.created_at.isoformat(),
                    conversation.metadata.updated_at.isoformat(),
                    conversation.metadata.last_activity.isoformat(),
                    conversation.metadata.message_count,
                    json.dumps(conversation.metadata.tags),
                    conversation.metadata.is_archived,
                    json.dumps(asdict(conversation.metadata))
                ))
                
                # 删除旧消息
                await db.execute(
                    "DELETE FROM conversation_messages WHERE conversation_id = ?",
                    (conversation.conversation_id,)
                )
                
                # 保存所有消息
                for i, message in enumerate(conversation.messages):
                    await db.execute("""
                        INSERT INTO conversation_messages 
                        (id, conversation_id, user_id, role, content, timestamp, sequence_number, message_metadata) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()),
                        conversation.conversation_id,
                        user_id,
                        message.role,
                        message.content,
                        message.timestamp.isoformat(),
                        i + 1,
                        json.dumps({})
                    ))
                
                await db.commit()
                logger.debug(f"对话保存成功: {conversation.conversation_id}")
                return True
        except Exception as e:
            logger.error(f"保存对话失败: {e}")
            return False
    
    async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Conversation]:
        """获取对话"""
        try:
            async with self.get_connection() as db:
                # 获取对话基本信息
                cursor = await db.execute(
                    "SELECT * FROM conversations WHERE conversation_id = ? AND user_id = ?",
                    (conversation_id, user_id)
                )
                conv_row = await cursor.fetchone()
                if not conv_row:
                    return None
                
                # 获取消息
                cursor = await db.execute(
                    "SELECT role, content, timestamp FROM conversation_messages WHERE conversation_id = ? ORDER BY sequence_number",
                    (conversation_id,)
                )
                message_rows = await cursor.fetchall()
                
                # 构造对话对象
                messages = []
                for row in message_rows:
                    messages.append(ChatMessage(
                        role=row[0],
                        content=row[1],
                        timestamp=datetime.fromisoformat(row[2])
                    ))
                
                metadata = ConversationMetadata(
                    title=conv_row[2],
                    created_at=datetime.fromisoformat(conv_row[3]),
                    updated_at=datetime.fromisoformat(conv_row[4]),
                    last_activity=datetime.fromisoformat(conv_row[5]),
                    message_count=conv_row[6],
                    tags=json.loads(conv_row[7]) if conv_row[7] else [],
                    is_archived=bool(conv_row[8])
                )
                
                return Conversation(
                    conversation_id=conversation_id,
                    messages=messages,
                    metadata=metadata
                )
        except Exception as e:
            logger.error(f"获取对话失败: {e}")
            return None
    
    async def list_conversations(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        """获取用户对话列表"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute("""
                    SELECT conversation_id, title, created_at, updated_at, last_activity, 
                           message_count, tags, is_archived 
                    FROM conversations 
                    WHERE user_id = ? AND is_archived = FALSE 
                    ORDER BY last_activity DESC 
                    LIMIT ? OFFSET ?
                """, (user_id, limit, offset))
                
                rows = await cursor.fetchall()
                conversations = []
                for row in rows:
                    conversations.append({
                        'conversation_id': row[0],
                        'title': row[1],
                        'created_at': row[2],
                        'updated_at': row[3],
                        'last_activity': row[4],
                        'message_count': row[5],
                        'tags': json.loads(row[6]) if row[6] else [],
                        'is_archived': bool(row[7])
                    })
                
                return conversations
        except Exception as e:
            logger.error(f"获取对话列表失败: {e}")
            return []
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """删除对话"""
        try:
            async with self.get_connection() as db:
                # 由于外键约束，删除对话会自动删除相关消息
                await db.execute(
                    "DELETE FROM conversations WHERE conversation_id = ? AND user_id = ?",
                    (conversation_id, user_id)
                )
                await db.commit()
                logger.info(f"对话删除成功: {conversation_id}")
                return True
        except Exception as e:
            logger.error(f"删除对话失败: {e}")
            return False
    
    # ===== 搜索历史管理 =====
    
    async def save_search_history(self, user_id: str, search_data: Dict) -> bool:
        """保存搜索历史"""
        try:
            async with self.get_connection() as db:
                await db.execute("""
                    INSERT INTO user_search_history 
                    (id, user_id, search_id, timestamp, original_query, expanded_keywords, papers, max_results, domain) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    user_id,
                    search_data.get('search_id', str(uuid.uuid4())),
                    search_data.get('timestamp', datetime.now().isoformat()),
                    search_data['original_query'],
                    json.dumps(search_data.get('expanded_keywords', [])),
                    json.dumps(search_data.get('papers', [])),
                    search_data.get('max_results', 20),
                    search_data.get('domain', 'unknown')
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"保存搜索历史失败: {e}")
            return False
    
    async def get_search_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """获取搜索历史"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute("""
                    SELECT search_id, timestamp, original_query, expanded_keywords, papers, max_results, domain 
                    FROM user_search_history 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (user_id, limit))
                
                rows = await cursor.fetchall()
                history = []
                for row in rows:
                    history.append({
                        'search_id': row[0],
                        'timestamp': row[1],
                        'original_query': row[2],
                        'expanded_keywords': json.loads(row[3]) if row[3] else [],
                        'papers': json.loads(row[4]) if row[4] else [],
                        'max_results': row[5],
                        'domain': row[6]
                    })
                
                return history
        except Exception as e:
            logger.error(f"获取搜索历史失败: {e}")
            return []
    
    # ===== 聊天历史管理 =====
    
    async def save_chat_history(self, user_id: str, chat_data: Dict) -> bool:
        """保存聊天历史"""
        try:
            async with self.get_connection() as db:
                await db.execute("""
                    INSERT OR REPLACE INTO user_chat_history 
                    (id, user_id, chat_id, timestamp, title, messages, last_activity, message_count) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    user_id,
                    chat_data['chat_id'],
                    chat_data.get('timestamp', datetime.now().isoformat()),
                    chat_data['title'],
                    json.dumps(chat_data['messages']),
                    chat_data.get('last_activity', datetime.now().isoformat()),
                    len(chat_data['messages'])
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"保存聊天历史失败: {e}")
            return False
    
    async def get_chat_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """获取聊天历史"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute("""
                    SELECT chat_id, timestamp, title, messages, last_activity, message_count 
                    FROM user_chat_history 
                    WHERE user_id = ? 
                    ORDER BY last_activity DESC 
                    LIMIT ?
                """, (user_id, limit))
                
                rows = await cursor.fetchall()
                history = []
                for row in rows:
                    history.append({
                        'chat_id': row[0],
                        'timestamp': row[1],
                        'title': row[2],
                        'messages': json.loads(row[3]) if row[3] else [],
                        'last_activity': row[4],
                        'message_count': row[5]
                    })
                
                return history
        except Exception as e:
            logger.error(f"获取聊天历史失败: {e}")
            return []
    
    # ===== 用户设置管理 =====
    
    async def save_user_settings(self, user_id: str, settings: Dict) -> bool:
        """保存用户设置"""
        try:
            async with self.get_connection() as db:
                await db.execute("""
                    INSERT OR REPLACE INTO user_settings 
                    (id, user_id, theme, language, settings, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    user_id,
                    settings.get('theme', 'dark'),
                    settings.get('language', 'zh'),
                    json.dumps(settings.get('settings', {})),
                    datetime.now().isoformat()
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"保存用户设置失败: {e}")
            return False
    
    async def get_user_settings(self, user_id: str) -> Optional[Dict]:
        """获取用户设置"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    "SELECT theme, language, settings FROM user_settings WHERE user_id = ?",
                    (user_id,)
                )
                row = await cursor.fetchone()
                if row:
                    return {
                        'theme': row[0],
                        'language': row[1],
                        'settings': json.loads(row[2]) if row[2] else {}
                    }
                return None
        except Exception as e:
            logger.error(f"获取用户设置失败: {e}")
            return None
    
    # ===== 用户行为日志 =====
    
    async def log_user_action(self, user_id: str, action: str, payload: Optional[Dict] = None) -> bool:
        """记录用户行为"""
        try:
            async with self.get_connection() as db:
                await db.execute("""
                    INSERT INTO user_actions (id, user_id, action, payload, created_at) 
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    user_id,
                    action,
                    json.dumps(payload) if payload else None,
                    datetime.now().isoformat()
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"记录用户行为失败: {e}")
            return False
    
    # ===== 工具方法 =====
    
    async def cleanup_old_data(self, days_to_keep: int = 90):
        """清理旧数据"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
            
            async with await self.get_connection() as db:
                # 清理旧的用户行为日志
                await db.execute(
                    "DELETE FROM user_actions WHERE created_at < ?",
                    (cutoff_date,)
                )
                
                # 清理旧的搜索历史（保留最近的记录）
                await db.execute("""
                    DELETE FROM user_search_history 
                    WHERE timestamp < ? AND id NOT IN (
                        SELECT id FROM user_search_history 
                        WHERE user_id IN (SELECT DISTINCT user_id FROM users) 
                        ORDER BY timestamp DESC 
                        LIMIT 100
                    )
                """, (cutoff_date,))
                
                await db.commit()
                logger.info(f"清理{days_to_keep}天前的旧数据完成")
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
    
    async def get_stats(self) -> Dict:
        """获取数据库统计信息"""
        try:
            async with self.get_connection() as db:
                stats = {}
                
                # 用户统计
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                stats['total_users'] = (await cursor.fetchone())[0]
                
                # 对话统计
                cursor = await db.execute("SELECT COUNT(*) FROM conversations")
                stats['total_conversations'] = (await cursor.fetchone())[0]
                
                # 消息统计
                cursor = await db.execute("SELECT COUNT(*) FROM conversation_messages")
                stats['total_messages'] = (await cursor.fetchone())[0]
                
                # 搜索统计
                cursor = await db.execute("SELECT COUNT(*) FROM user_search_history")
                stats['total_searches'] = (await cursor.fetchone())[0]
                
                # 活跃用户（最近7天）
                recent_date = (datetime.now() - timedelta(days=7)).isoformat()
                cursor = await db.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM user_actions WHERE created_at > ?",
                    (recent_date,)
                )
                stats['active_users_7d'] = (await cursor.fetchone())[0]
                
                return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

# 全局单例实例
_sqlite_manager: Optional[SQLiteManager] = None

async def get_sqlite_manager() -> SQLiteManager:
    """获取SQLite管理器单例"""
    global _sqlite_manager
    if _sqlite_manager is None:
        _sqlite_manager = SQLiteManager()
        await _sqlite_manager.initialize()
    return _sqlite_manager

# 初始化示例邀请码的函数
async def initialize_invite_codes():
    """初始化示例邀请码（仅在开发环境使用）"""
    manager = await get_sqlite_manager()
    
    sample_codes = [
        ("VERITEX001", "Veritex内测码1 - 主要测试用"),
        ("VERITEX002", "Veritex内测码2 - 次要测试用"),
        ("VERITEX003", "Veritex内测码3 - 备用测试"),
        ("DEMO2024", "演示用邀请码"),
        ("TEST123", "测试邀请码")
    ]
    
    try:
        async with await manager.get_connection() as db:
            for code, description in sample_codes:
                # 检查是否已存在
                cursor = await db.execute("SELECT code FROM invite_codes WHERE code = ?", (code,))
                if not await cursor.fetchone():
                    await db.execute(
                        "INSERT INTO invite_codes (code, description) VALUES (?, ?)",
                        (code, description)
                    )
            
            await db.commit()
            logger.info("示例邀请码初始化完成")
    
    except Exception as e:
        logger.error(f"初始化邀请码失败: {e}")

if __name__ == "__main__":
    async def test_sqlite_manager():
        """测试SQLite管理器"""
        manager = await get_sqlite_manager()
        await initialize_invite_codes()
        
        # 测试用户创建
        user_id = "test_user_001"
        success = await manager.create_user(user_id, "TEST123")
        print(f"用户创建: {success}")
        
        # 测试统计信息
        stats = await manager.get_stats()
        print(f"数据库统计: {stats}")
    
    # 运行测试
    asyncio.run(test_sqlite_manager())