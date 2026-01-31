"""
Enhanced Analytics Module for Knowledge OS Dashboard
Расширенная аналитика и метрики для Dashboard
"""

import logging
import os
from typing import Dict, List

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

def get_db_connection():
    """Получение подключения к БД"""
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

class EnhancedAnalytics:
    """Класс для расширенной аналитики"""

    @staticmethod
    def fetch_data(query: str, params=None) -> List[Dict]:
        """Выполнение запроса к БД"""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchall()
        except (psycopg2.Error, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
            logger.error("Database error in fetch_data: %s", e, exc_info=True)
            return []
        except Exception as e:
            logger.critical("Unexpected error in fetch_data: %s", e, exc_info=True)
            return []

    @staticmethod
    def get_system_overview() -> Dict:
        """Общий обзор системы"""
        data = EnhancedAnalytics.fetch_data("""
            SELECT 
                (SELECT count(*) FROM knowledge_nodes) as total_nodes,
                (SELECT count(*) FROM experts) as total_experts,
                (SELECT count(*) FROM domains) as total_domains,
                (SELECT count(*) FROM tasks WHERE status = 'pending') as pending_tasks,
                (SELECT count(*) FROM tasks WHERE status = 'completed') as completed_tasks,
                (SELECT sum(usage_count) FROM knowledge_nodes) as total_usage,
                (SELECT avg(confidence_score) FROM knowledge_nodes) as avg_confidence,
                (SELECT count(*) FROM knowledge_nodes WHERE is_verified = TRUE) as verified_nodes
        """)

        if data:
            return dict(data[0])
        return {}
    @staticmethod
    def get_knowledge_growth_trend(days: int = 30) -> pd.DataFrame:
        """Тренд роста базы знаний"""
        data = EnhancedAnalytics.fetch_data("""
            SELECT 
                DATE(created_at) as date,
                count(*) as new_nodes,
                sum(usage_count) as total_usage,
                avg(confidence_score) as avg_confidence
            FROM knowledge_nodes
            WHERE created_at >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(created_at)
            ORDER BY date
        """, (days,))

        return pd.DataFrame(data) if data else pd.DataFrame()

    @staticmethod
    def get_domain_distribution() -> pd.DataFrame:
        """Распределение знаний по доменам"""
        data = EnhancedAnalytics.fetch_data("""
            SELECT 
                d.name as domain,
                count(k.id) as node_count,
                sum(k.usage_count) as total_usage,
                avg(k.confidence_score) as avg_confidence,
                count(k.id) FILTER (WHERE k.is_verified = TRUE) as verified_count
            FROM domains d
            LEFT JOIN knowledge_nodes k ON d.id = k.domain_id
            GROUP BY d.id, d.name
            ORDER BY node_count DESC
        """)

        return pd.DataFrame(data) if data else pd.DataFrame()

    @staticmethod
    def get_expert_performance() -> pd.DataFrame:
        """Производительность экспертов"""
        data = EnhancedAnalytics.fetch_data("""
            SELECT 
                e.name,
                e.department,
                e.role,
                count(DISTINCT k.id) as knowledge_created,
                sum(k.usage_count) as total_usage,
                avg(k.confidence_score) as avg_confidence,
                count(t.id) FILTER (WHERE t.status = 'completed') as tasks_completed,
                count(t.id) FILTER (WHERE t.status = 'pending') as tasks_pending
            FROM experts e
            LEFT JOIN knowledge_nodes k ON k.metadata->>'expert_id' = e.id::text
            LEFT JOIN tasks t ON t.assignee_expert_id = e.id
            GROUP BY e.id, e.name, e.department, e.role
            ORDER BY total_usage DESC NULLS LAST
        """, None)

        return pd.DataFrame(data) if data else pd.DataFrame()

    @staticmethod
    def get_search_effectiveness() -> Dict:
        """Эффективность поиска"""
        data = EnhancedAnalytics.fetch_data("""
            SELECT 
                count(DISTINCT k.id) as total_searchable_nodes,
                count(DISTINCT k.id) FILTER (WHERE k.usage_count > 0) as used_nodes,
                avg(k.usage_count) as avg_usage_per_node,
                count(DISTINCT k.id) FILTER (WHERE k.usage_count > 10) as popular_nodes,
                avg(k.confidence_score) FILTER (WHERE k.usage_count > 0) as avg_confidence_used
            FROM knowledge_nodes k
        """)

        if data:
            result = dict(data[0])
            if result.get('total_searchable_nodes', 0) > 0:
                result['usage_rate'] = (
                    result.get('used_nodes', 0) / result['total_searchable_nodes'] * 100
                )
            return result
        return {}

    @staticmethod
    def get_quality_metrics() -> Dict:
        """Метрики качества знаний"""
        data = EnhancedAnalytics.fetch_data("""
            SELECT 
                count(*) FILTER (WHERE confidence_score >= 0.8) as high_quality,
                count(*) FILTER (WHERE confidence_score >= 0.5 AND confidence_score < 0.8) as medium_quality,
                count(*) FILTER (WHERE confidence_score < 0.5) as low_quality,
                count(*) FILTER (WHERE is_verified = TRUE) as verified,
                count(*) FILTER (WHERE metadata->>'auto_fixed' = 'true') as auto_fixed,
                count(*) FILTER (WHERE metadata->>'adversarial_tested' = 'true') as tested,
                count(*) FILTER (WHERE metadata->>'survived' = 'false') as destroyed
            FROM knowledge_nodes
        """)

        if data:
            result = dict(data[0])
            total = sum([
                result.get('high_quality', 0),
                result.get('medium_quality', 0),
                result.get('low_quality', 0)
            ])
            if total > 0:
                result['high_quality_pct'] = result.get('high_quality', 0) / total * 100
                result['medium_quality_pct'] = result.get('medium_quality', 0) / total * 100
                result['low_quality_pct'] = result.get('low_quality', 0) / total * 100
            return result
        return {}

    @staticmethod
    def get_task_analytics() -> Dict:
        """Аналитика задач"""
        data = EnhancedAnalytics.fetch_data("""
            SELECT 
                count(*) FILTER (WHERE status = 'pending') as pending,
                count(*) FILTER (WHERE status = 'in_progress') as in_progress,
                count(*) FILTER (WHERE status = 'completed') as completed,
                count(*) FILTER (WHERE status = 'failed') as failed,
                count(*) FILTER (WHERE priority = 'urgent') as urgent,
                count(*) FILTER (WHERE priority = 'high') as high_priority,
                count(*) FILTER (WHERE priority = 'medium') as medium_priority,
                count(*) FILTER (WHERE priority = 'low') as low_priority,
                avg(EXTRACT(EPOCH FROM (completed_at - created_at))/3600)
                    FILTER (WHERE status = 'completed') as avg_completion_hours
            FROM tasks
        """)

        if data:
            result = dict(data[0])
            total = sum([
                result.get('pending', 0),
                result.get('in_progress', 0),
                result.get('completed', 0),
                result.get('failed', 0)
            ])
            if total > 0:
                result['completion_rate'] = result.get('completed', 0) / total * 100
            return result
        return {}

    @staticmethod
    def get_trends_forecast(days: int = 7) -> Dict:
        """Прогноз трендов"""
        # Получаем данные за последние дни
        growth_data = EnhancedAnalytics.get_knowledge_growth_trend(days * 2)

        if len(growth_data) < 2:
            return {}

        # Простой линейный прогноз
        recent_growth = growth_data['new_nodes'].tail(days).mean()
        forecast = {
            'current_daily_growth': recent_growth,
            'forecast_7_days': recent_growth * 7,
            'forecast_30_days': recent_growth * 30,
        }

        # Прогноз использования
        recent_usage = growth_data['total_usage'].tail(days).mean()
        forecast['forecast_usage_7_days'] = recent_usage * 7

        return forecast

    @staticmethod
    def get_knowledge_graph_data(limit: int = 50) -> Dict:
        """Данные для графа знаний (использует таблицу knowledge_links)"""
        # Получаем узлы знаний, которые имеют связи
        nodes_data = EnhancedAnalytics.fetch_data("""
            SELECT DISTINCT
                k.id,
                k.content,
                d.name as domain,
                k.confidence_score,
                COALESCE((k.metadata->>'usage_count')::int, 0) as usage_count
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.id IN (
                SELECT DISTINCT source_node_id FROM knowledge_links
                UNION
                SELECT DISTINCT target_node_id FROM knowledge_links
            )
            ORDER BY usage_count DESC, k.confidence_score DESC
            LIMIT %s
        """, (limit,))

        # Получаем связи между узлами
        links_data = EnhancedAnalytics.fetch_data("""
            SELECT 
                kl.source_node_id,
                kl.target_node_id,
                kl.link_type,
                kl.strength
            FROM knowledge_links kl
            WHERE kl.source_node_id IN (
                SELECT id FROM knowledge_nodes 
                ORDER BY COALESCE((metadata->>'usage_count')::int, 0) DESC, confidence_score DESC
                LIMIT %s
            )
            OR kl.target_node_id IN (
                SELECT id FROM knowledge_nodes 
                ORDER BY COALESCE((metadata->>'usage_count')::int, 0) DESC, confidence_score DESC
                LIMIT %s
            )
        """, (limit, limit))

        nodes = []
        edges = []
        node_ids = set()

        # Добавляем узлы
        for node in nodes_data:
            node_id = str(node['id'])
            node_ids.add(node_id)
            label = node['content']
            if len(label) > 50:
                label = label[:50] + '...'
            nodes.append({
                'id': node_id,
                'label': label,
                'domain': node['domain'],
                'confidence': float(node['confidence_score']) if node['confidence_score'] else 0.5,
                'usage': node['usage_count'] or 0
            })

        # Добавляем связи
        for link in links_data:
            source_id = str(link['source_node_id'])
            target_id = str(link['target_node_id'])

            # Добавляем узлы, если их еще нет
            if source_id not in node_ids:
                source_node = EnhancedAnalytics.fetch_data("""
                    SELECT k.id, k.content, d.name as domain, k.confidence_score,
                           COALESCE((k.metadata->>'usage_count')::int, 0) as usage_count
                    FROM knowledge_nodes k
                    JOIN domains d ON k.domain_id = d.id
                    WHERE k.id = %s
                """, (source_id,))
                if source_node:
                    node_ids.add(source_id)
                    s_content = source_node[0]['content']
                    s_label = (s_content[:50] + '...') if len(s_content) > 50 else s_content
                    s_conf = source_node[0]['confidence_score']
                    nodes.append({
                        'id': source_id,
                        'label': s_label,
                        'domain': source_node[0]['domain'],
                        'confidence': float(s_conf) if s_conf else 0.5,
                        'usage': source_node[0]['usage_count'] or 0
                    })

            if target_id not in node_ids:
                target_node = EnhancedAnalytics.fetch_data("""
                    SELECT k.id, k.content, d.name as domain, k.confidence_score,
                           COALESCE((k.metadata->>'usage_count')::int, 0) as usage_count
                    FROM knowledge_nodes k
                    JOIN domains d ON k.domain_id = d.id
                    WHERE k.id = %s
                """, (target_id,))
                if target_node:
                    node_ids.add(target_id)
                    t_content = target_node[0]['content']
                    t_label = (t_content[:50] + '...') if len(t_content) > 50 else t_content
                    t_conf = target_node[0]['confidence_score']
                    nodes.append({
                        'id': target_id,
                        'label': t_label,
                        'domain': target_node[0]['domain'],
                        'confidence': float(t_conf) if t_conf else 0.5,
                        'usage': target_node[0]['usage_count'] or 0
                    })

            edges.append({
                'source': source_id,
                'target': target_id,
                'type': link['link_type'],
                'strength': float(link['strength']) if link['strength'] else 1.0
            })

        return {'nodes': nodes, 'edges': edges}
