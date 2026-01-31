"""
REST API для внешних систем

Функционал:
- REST API endpoints для работы с Knowledge OS
- Аутентификация через API keys
- Документация через OpenAPI/Swagger
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncpg
import os
import sys
import json
from datetime import datetime

# Чтобы token_logger и evaluator импортировались (Singularity 9.0 log_interaction)
_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

app = FastAPI(
    title="Knowledge OS REST API",
    description="REST API для интеграции с Knowledge OS",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
API_KEY = os.getenv('API_KEY', 'your-secret-api-key')

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
security = HTTPBearer()


async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Проверка API ключа (legacy)"""
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key


async def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка JWT токена"""
    from security import SecurityManager
    
    security_manager = SecurityManager()
    payload = security_manager.verify_jwt_token(credentials.credentials)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return payload


# Pydantic модели
class KnowledgeNodeCreate(BaseModel):
    content: str
    domain: str
    confidence_score: float = 1.0
    metadata: Dict[str, Any] = {}


class KnowledgeNodeResponse(BaseModel):
    id: str
    content: str
    domain: str
    confidence_score: float
    created_at: datetime


class SearchRequest(BaseModel):
    query: str
    domain: Optional[str] = None
    limit: int = 5


class WebhookCreate(BaseModel):
    webhook_type: str
    url: str
    events: List[str] = []
    metadata: Dict[str, Any] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str = "user"


class LogInteractionRequest(BaseModel):
    """Лог взаимодействия для Singularity 9.0 (Web IDE, MCP и др.)"""
    prompt: str
    response: str
    expert_name: Optional[str] = None
    source: str = "web_ide"


async def _ensure_orchestrator_version_migration():
    """При старте API: применить миграцию orchestrator_version если колонки нет."""
    try:
        conn = await asyncpg.connect(DB_URL)
        row = await conn.fetchrow(
            """SELECT 1 FROM information_schema.columns
               WHERE table_name = 'tasks' AND column_name = 'orchestrator_version'"""
        )
        if row is None:
            await conn.execute(
                "ALTER TABLE tasks ADD COLUMN orchestrator_version VARCHAR(20) DEFAULT NULL"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_orchestrator_version ON tasks (orchestrator_version) WHERE orchestrator_version IS NOT NULL"
            )
        await conn.close()
    except Exception:
        pass


@app.on_event("startup")
async def startup_migrations():
    await _ensure_orchestrator_version_migration()


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "name": "Knowledge OS REST API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья API"""
    try:
        conn = await asyncpg.connect(DB_URL)
        await conn.execute("SELECT 1")
        await conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def _ab_metrics_prometheus(hours: int = 24) -> str:
    """A/B метрики из tasks (orchestrator_version) в формате Prometheus."""
    lines = []
    try:
        conn = await asyncpg.connect(DB_URL)
        query = """
        SELECT orchestrator_version,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'completed') AS completed,
               AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) FILTER (WHERE completed_at IS NOT NULL) AS avg_duration
        FROM tasks
        WHERE created_at > NOW() - make_interval(hours => $1)
          AND orchestrator_version IN ('v2', 'existing')
        GROUP BY orchestrator_version
        """
        rows = await conn.fetch(query, hours)
        await conn.close()
        v2_total = v2_success = v2_dur = 0
        ex_total = ex_success = ex_dur = 0
        for r in rows:
            ver = (r["orchestrator_version"] or "").strip().lower()
            total = r["total"] or 0
            completed = r["completed"] or 0
            avg_d = float(r["avg_duration"] or 0)
            if ver == "v2":
                v2_total, v2_success, v2_dur = total, completed, avg_d
            else:
                ex_total, ex_success, ex_dur = total, completed, avg_d
        v2_sr = v2_success / v2_total if v2_total else 0
        ex_sr = ex_success / ex_total if ex_total else 0
        lines = [
            f"orchestration_v2_tasks_total {v2_total}",
            f"orchestration_existing_tasks_total {ex_total}",
            f"orchestration_v2_success_rate {v2_sr:.4f}",
            f"orchestration_existing_success_rate {ex_sr:.4f}",
            f"orchestration_v2_avg_duration_seconds {v2_dur:.2f}",
            f"orchestration_existing_avg_duration_seconds {ex_dur:.2f}",
        ]
    except Exception as e:
        lines = [f"# A/B metrics error: {e}"]
    return "\n".join(lines)


async def _orchestration_metrics_prometheus() -> str:
    """Оркестрация + A/B в формате Prometheus (для /metrics и /api/v2/orchestrate/metrics)."""
    try:
        try:
            from task_orchestration import OrchestrationMonitor
        except ImportError:
            from app.task_orchestration import OrchestrationMonitor
        monitor = OrchestrationMonitor()
        text = await monitor.export_to_prometheus()
        ab_text = await _ab_metrics_prometheus(24)
        return text + "\n# A/B (last 24h)\n" + ab_text
    except Exception as e:
        return f"# ERROR: {e}\n"


@app.get("/metrics")
async def metrics_prometheus():
    """
    Метрики в формате Prometheus (скрапится Prometheus по умолчанию).
    Включает оркестрацию и A/B (orchestrator_version).
    """
    text = await _orchestration_metrics_prometheus()
    return Response(content=text, media_type="text/plain; charset=utf-8")


@app.get("/api/v2/orchestrate/metrics")
async def orchestration_metrics():
    """
    Метрики оркестрации в формате Prometheus для Grafana.
    OrchestrationMonitor + A/B метрики из tasks (orchestrator_version).
    """
    text = await _orchestration_metrics_prometheus()
    return Response(content=text, media_type="text/plain; charset=utf-8")


@app.post("/api/log_interaction")
async def log_interaction(body: LogInteractionRequest):
    """
    Логирует взаимодействие в interaction_logs (Singularity 9.0).
    Вызывается бэкендом Web IDE после ответа Victoria/MLX — метрики появятся на дашборде.
    """
    import logging
    _log = logging.getLogger(__name__)
    _log.info("[LOG_INTERACTION] entry prompt_len=%s response_len=%s source=%s", len(body.prompt), len(body.response), body.source)
    try:
        from token_logger import log_ai_interaction
        log_id = await log_ai_interaction(
            prompt=body.prompt[:10000],
            response=body.response[:20000],
            expert_name=body.expert_name,
            model_type="local",
            source=body.source,
            metadata={"source": body.source},
        )
        _log.info("[LOG_INTERACTION] success log_id=%s", log_id)
        return {"ok": True, "log_id": log_id}
    except Exception as e:
        _log.exception("[LOG_INTERACTION] exception: %s", e)
        return {"ok": False, "error": str(e)}


@app.post("/auth/login")
async def login(credentials: LoginRequest):
    """Аутентификация пользователя"""
    try:
        from security import SecurityManager, Role
        
        security = SecurityManager()
        user = await security.authenticate_user(credentials.username, credentials.password)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = security.generate_jwt_token(
            user['user_id'],
            user['username'],
            user['role']
        )
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": user['user_id'],
                "username": user['username'],
                "role": user['role'].value
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/register")
async def register(user_data: RegisterRequest):
    """Регистрация нового пользователя"""
    try:
        from security import SecurityManager, Role
        
        security = SecurityManager()
        
        # Проверяем роль
        try:
            role = Role(user_data.role)
        except ValueError:
            role = Role.USER
        
        user_id = await security.create_user(
            user_data.username,
            user_data.password,
            role,
            user_data.email
        )
        
        if not user_id:
            raise HTTPException(status_code=400, detail="Failed to create user")
        
        return {
            "user_id": user_id,
            "username": user_data.username,
            "role": role.value,
            "status": "created"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/audit", dependencies=[Depends(verify_jwt_token)])
async def get_audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    token: Dict = Depends(verify_jwt_token)
):
    """Получение логов аудита (только для админов)"""
    try:
        from security import SecurityManager, Role, Permission
        
        security = SecurityManager()
        
        # Проверяем права доступа
        user_role = Role(token['role'])
        if not security.has_permission(user_role, Permission.ADMIN_ACCESS):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        logs = await security.get_audit_logs(user_id, action, limit)
        
        return {
            "logs": logs,
            "count": len(logs)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge", response_model=KnowledgeNodeResponse, dependencies=[Depends(verify_jwt_token)])
async def create_knowledge(knowledge: KnowledgeNodeCreate):
    """Создание нового знания"""
    try:
        conn = await asyncpg.connect(DB_URL)
        try:
            # Получаем или создаем домен
            domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", knowledge.domain)
            if not domain_id:
                domain_id = await conn.fetchval("INSERT INTO domains (name) VALUES ($1) RETURNING id", knowledge.domain)
            
            # Создаем знание
            knowledge_id = await conn.fetchval("""
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, domain_id, knowledge.content, knowledge.confidence_score, json.dumps(knowledge.metadata))
            
            return KnowledgeNodeResponse(
                id=str(knowledge_id),
                content=knowledge.content,
                domain=knowledge.domain,
                confidence_score=knowledge.confidence_score,
                created_at=datetime.now()
            )
        finally:
            await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/knowledge/{knowledge_id}", response_model=KnowledgeNodeResponse, dependencies=[Depends(verify_jwt_token)])
async def get_knowledge(knowledge_id: str):
    """Получение знания по ID"""
    try:
        conn = await asyncpg.connect(DB_URL)
        try:
            row = await conn.fetchrow("""
                SELECT k.id, k.content, d.name as domain, k.confidence_score, k.created_at
                FROM knowledge_nodes k
                JOIN domains d ON k.domain_id = d.id
                WHERE k.id = $1
            """, knowledge_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Knowledge not found")
            
            return KnowledgeNodeResponse(
                id=str(row['id']),
                content=row['content'],
                domain=row['domain'],
                confidence_score=row['confidence_score'],
                created_at=row['created_at']
            )
        finally:
            await conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", dependencies=[Depends(verify_jwt_token)])
async def search_knowledge(request: SearchRequest):
    """Поиск знаний"""
    try:
        conn = await asyncpg.connect(DB_URL)
        try:
            query = """
                SELECT k.id, k.content, d.name as domain, k.confidence_score
                FROM knowledge_nodes k
                JOIN domains d ON k.domain_id = d.id
                WHERE k.content ILIKE $1
            """
            params = [f"%{request.query}%"]
            
            if request.domain:
                query += " AND d.name = $2"
                params.append(request.domain)
            
            query += " ORDER BY k.confidence_score DESC LIMIT $3"
            params.append(request.limit)
            
            rows = await conn.fetch(query, *params)
            
            return {
                "query": request.query,
                "results": [
                    {
                        "id": str(row['id']),
                        "content": row['content'],
                        "domain": row['domain'],
                        "confidence_score": row['confidence_score']
                    }
                    for row in rows
                ]
            }
        finally:
            await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks", dependencies=[Depends(verify_jwt_token)])
async def create_webhook(webhook: WebhookCreate):
    """Создание webhook"""
    try:
        from webhook_manager import WebhookManager, WebhookType
        
        manager = WebhookManager()
        webhook_id = await manager.register_webhook(
            WebhookType(webhook.webhook_type),
            webhook.url,
            webhook.events,
            webhook.metadata
        )
        
        if webhook_id:
            return {"webhook_id": webhook_id, "status": "created"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create webhook")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", dependencies=[Depends(verify_jwt_token)])
async def get_stats():
    """Получение статистики системы"""
    try:
        conn = await asyncpg.connect(DB_URL)
        try:
            stats = await conn.fetchrow("""
                SELECT 
                    (SELECT count(*) FROM knowledge_nodes) as total_knowledge,
                    (SELECT count(*) FROM experts) as total_experts,
                    (SELECT count(*) FROM domains) as total_domains,
                    (SELECT count(*) FROM tasks WHERE status = 'pending') as pending_tasks,
                    (SELECT count(*) FROM tasks WHERE status = 'completed') as completed_tasks
            """)
            
            return {
                "total_knowledge": stats['total_knowledge'] or 0,
                "total_experts": stats['total_experts'] or 0,
                "total_domains": stats['total_domains'] or 0,
                "pending_tasks": stats['pending_tasks'] or 0,
                "completed_tasks": stats['completed_tasks'] or 0
            }
        finally:
            await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

