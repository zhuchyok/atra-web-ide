"""
Collaboration Forum
Система коллаборации и обмена опытом между агентами
AGENT IMPROVEMENTS: Система коллаборации и обмена опытом
"""

import asyncio
import logging
import os
import json
import hashlib
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

@dataclass
class ForumPost:
    """Пост в форуме агентов"""
    post_id: str
    agent_id: str
    title: str
    content: str
    category: str  # 'solution', 'question', 'best_practice', 'issue'
    tags: List[str]
    created_at: datetime
    upvotes: int = 0
    downvotes: int = 0
    helpful_count: int = 0

@dataclass
class ForumComment:
    """Комментарий к посту"""
    comment_id: str
    post_id: str
    agent_id: str
    content: str
    created_at: datetime
    helpful_count: int = 0

class CollaborationForum:
    """
    Система коллаборации и обмена опытом.
    
    Функционал:
    - Форум/чат для обмена опытом между агентами
    - Автоматическое распространение успешных решений
    - Система вопросов и ответов
    - Рейтинг полезности советов
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self._posts_cache: Dict[str, ForumPost] = {}
        
    async def _get_conn(self):
        """Получить подключение к БД"""
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None
        try:
            conn = await asyncpg.connect(self.db_url)
            return conn
        except Exception as e:
            logger.error(f"❌ [COLLAB FORUM] Ошибка подключения к БД: {e}")
            return None
    
    async def create_post(
        self,
        agent_id: str,
        title: str,
        content: str,
        category: str = 'best_practice',
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Создает пост в форуме.
        
        Args:
            agent_id: ID агента
            title: Заголовок поста
            content: Содержание поста
            category: Категория ('solution', 'question', 'best_practice', 'issue')
            tags: Теги
        
        Returns:
            post_id
        """
        try:
            # Генерируем post_id
            post_key = f"{agent_id}:{title}:{datetime.now(timezone.utc).isoformat()}"
            post_id = hashlib.md5(post_key.encode()).hexdigest()[:16]
            
            post = ForumPost(
                post_id=post_id,
                agent_id=agent_id,
                title=title,
                content=content,
                category=category,
                tags=tags or [],
                created_at=datetime.now(timezone.utc)
            )
            
            # Сохраняем в БД
            conn = await self._get_conn()
            if not conn:
                return post_id
            
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'agent_forum_posts'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        INSERT INTO agent_forum_posts (post_id, agent_id, title, content, category, tags, created_at, upvotes, downvotes, helpful_count)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (post_id) DO UPDATE
                        SET title = EXCLUDED.title, content = EXCLUDED.content
                    """, post_id, agent_id, title, content, category, json.dumps(tags or []), post.created_at, 0, 0, 0)
                
                self._posts_cache[post_id] = post
                
                logger.info(f"✅ [COLLAB FORUM] Создан пост {post_id} от агента {agent_id}")
                return post_id
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [COLLAB FORUM] Ошибка создания поста: {e}")
            return ""
    
    async def share_successful_solution(
        self,
        agent_id: str,
        problem: str,
        solution: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Распространяет успешное решение в форуме.
        
        Args:
            agent_id: ID агента, нашедшего решение
            problem: Описание проблемы
            solution: Решение
            context: Контекст (метрики улучшения, условия применения)
        
        Returns:
            post_id
        """
        title = f"Решение проблемы: {problem}"
        content = f"""
**Проблема:**
{problem}

**Решение:**
{solution}

**Контекст:**
{json.dumps(context or {}, indent=2)}
"""
        
        tags = ['solution', 'success', 'shared']
        if context:
            tags.extend(context.get('tags', []))
        
        return await self.create_post(agent_id, title, content, category='solution', tags=tags)
    
    async def get_popular_solutions(self, limit: int = 10) -> List[ForumPost]:
        """
        Получает популярные решения (по рейтингу).
        
        Args:
            limit: Максимальное количество
        
        Returns:
            Список постов
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return []
            
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'agent_forum_posts'
                    )
                """)
                
                if not table_exists:
                    return []
                
                rows = await conn.fetch("""
                    SELECT post_id, agent_id, title, content, category, tags, created_at, upvotes, downvotes, helpful_count
                    FROM agent_forum_posts
                    WHERE category = 'solution'
                    ORDER BY (upvotes - downvotes) DESC, helpful_count DESC
                    LIMIT $1
                """, limit)
                
                posts = []
                for row in rows:
                    post = ForumPost(
                        post_id=row['post_id'],
                        agent_id=row['agent_id'],
                        title=row['title'],
                        content=row['content'],
                        category=row['category'],
                        tags=json.loads(row['tags']) if isinstance(row['tags'], str) else row['tags'],
                        created_at=row['created_at'],
                        upvotes=row['upvotes'] or 0,
                        downvotes=row['downvotes'] or 0,
                        helpful_count=row['helpful_count'] or 0
                    )
                    posts.append(post)
                    self._posts_cache[post.post_id] = post
                
                return posts
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [COLLAB FORUM] Ошибка получения популярных решений: {e}")
            return []
    
    async def upvote_post(self, post_id: str, agent_id: str) -> bool:
        """
        Голосует за пост (upvote).
        
        Args:
            post_id: ID поста
            agent_id: ID агента
        
        Returns:
            True если успешно
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return False
            
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'agent_forum_posts'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        UPDATE agent_forum_posts
                        SET upvotes = upvotes + 1
                        WHERE post_id = $1
                    """, post_id)
                    
                    if post_id in self._posts_cache:
                        self._posts_cache[post_id].upvotes += 1
                    
                    logger.debug(f"✅ [COLLAB FORUM] Пост {post_id} получил upvote от {agent_id}")
                    return True
                
                return False
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [COLLAB FORUM] Ошибка upvote: {e}")
            return False
    
    async def mark_as_helpful(self, post_id: str, agent_id: str) -> bool:
        """
        Отмечает пост как полезный.
        
        Args:
            post_id: ID поста
            agent_id: ID агента
        
        Returns:
            True если успешно
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return False
            
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'agent_forum_posts'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        UPDATE agent_forum_posts
                        SET helpful_count = helpful_count + 1
                        WHERE post_id = $1
                    """, post_id)
                    
                    if post_id in self._posts_cache:
                        self._posts_cache[post_id].helpful_count += 1
                    
                    logger.debug(f"✅ [COLLAB FORUM] Пост {post_id} отмечен как полезный агентом {agent_id}")
                    return True
                
                return False
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [COLLAB FORUM] Ошибка отметки полезности: {e}")
            return False

# Singleton instance
_collab_forum_instance: Optional[CollaborationForum] = None

def get_collaboration_forum(db_url: str = DB_URL) -> CollaborationForum:
    """Получить singleton экземпляр CollaborationForum"""
    global _collab_forum_instance
    if _collab_forum_instance is None:
        _collab_forum_instance = CollaborationForum(db_url=db_url)
    return _collab_forum_instance

