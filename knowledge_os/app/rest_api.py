"""
REST API для внешних систем

Функционал:
- REST API endpoints для работы с Knowledge OS
- Аутентификация через API keys
- Документация через OpenAPI/Swagger
"""

from contextlib import asynccontextmanager
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


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup: миграции. Shutdown: закрыть общий HTTP-клиент (мировая практика: lifespan вместо on_event)."""
    await _ensure_orchestrator_version_migration()
    await _ensure_projects_table_migration()
    await _ensure_project_context_on_tasks_migration()
    yield
    try:
        from http_client import close_http_client
        await close_http_client()
    except Exception:
        pass


app = FastAPI(
    title="Knowledge OS REST API",
    description="REST API для интеграции с Knowledge OS",
    version="1.0.0",
    lifespan=_lifespan,
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

# Единый пул БД (при переходе на Rust — замена в db_pool.py)
async def _get_db():
    from db_pool import get_pool
    return await get_pool()

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


class BoardConsultRequest(BaseModel):
    """Запрос на консультацию Совета Директоров"""
    question: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None
    source: Optional[str] = "api"  # chat | api | nightly | dashboard


class BoardConsultResponse(BaseModel):
    """Ответ от Совета Директоров"""
    directive_text: str
    structured_decision: Dict[str, Any]
    risk_level: Optional[str] = None
    recommend_human_review: bool = False
    correlation_id: Optional[str] = None


class RegisterProjectRequest(BaseModel):
    """Регистрация проекта в реестре (таблица projects)."""
    slug: str
    name: str
    description: Optional[str] = None
    workspace_path: Optional[str] = None


class ProjectListItem(BaseModel):
    """Элемент списка проектов (GET /api/projects)."""
    slug: str
    name: str
    description: Optional[str] = None
    workspace_path: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


async def _ensure_orchestrator_version_migration():
    """При старте API: применить миграцию orchestrator_version если колонки нет."""
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
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
    except Exception:
        pass


async def _ensure_projects_table_migration():
    """При старте API: создать таблицу projects (реестр проектов), если её нет."""
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'projects'"
            )
            if row is None:
                migration_path = os.path.join(
                    os.path.dirname(__file__), "..", "db", "migrations", "add_projects_table.sql"
                )
                if os.path.exists(migration_path):
                    with open(migration_path, "r", encoding="utf-8") as f:
                        sql = f.read()
                    await conn.execute(sql)
    except Exception:
        pass


async def _ensure_project_context_on_tasks_migration():
    """При старте API: добавить колонку project_context в tasks, если её нет."""
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'tasks' AND column_name = 'project_context'"""
            )
            if row is None:
                migration_path = os.path.join(
                    os.path.dirname(__file__), "..", "db", "migrations", "add_project_context_to_tasks.sql"
                )
                if os.path.exists(migration_path):
                    with open(migration_path, "r", encoding="utf-8") as f:
                        sql = f.read()
                    await conn.execute(sql)
    except Exception:
        pass


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
        pool = await _get_db()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/api/models")
async def get_available_models():
    """
    Получить список реально доступных моделей с MLX и Ollama серверов.
    Данные кэшируются на 2 минуты (TTL=120сек).
    
    Полезно для:
    - Проверки какие модели загружены
    - Отладки выбора моделей
    - Мониторинга состояния серверов
    """
    import os
    
    # URL для Docker контейнера
    mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
    ollama_url = os.getenv("OLLAMA_API_URL", "http://host.docker.internal:11434")
    
    try:
        from available_models_scanner import scan_and_select_models
        
        # Получаем полный отчёт о моделях с правильными URL
        selection = await scan_and_select_models(
            mlx_url=mlx_url,
            ollama_url=ollama_url,
            force_refresh=True
        )
        
        return {
            "status": "success",
            "mlx": {
                "url": mlx_url,
                "models": selection.mlx_models,
                "count": len(selection.mlx_models) if selection.mlx_models else 0,
                "best_model": selection.mlx_best,
            },
            "ollama": {
                "url": ollama_url,
                "models": selection.ollama_models,
                "count": len(selection.ollama_models) if selection.ollama_models else 0,
                "best_model": selection.ollama_best,
            },
            "cache_ttl_seconds": 120,
            "note": "Модели сканируются автоматически каждые 2 минуты. Удаление/добавление модели будет замечено при следующем скане."
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "mlx": {"models": [], "count": 0, "url": mlx_url},
            "ollama": {"models": [], "count": 0, "url": ollama_url}
        }


async def _ab_metrics_prometheus(hours: int = 24) -> str:
    """A/B метрики из tasks (orchestrator_version) в формате Prometheus."""
    lines = []
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
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


@app.get("/api/projects", response_model=List[ProjectListItem])
async def list_projects():
    """
    Список зарегистрированных проектов (is_active=true).
    Используется дашбордом и клиентами для фильтра задач и выбора project_context.
    """
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT slug, name, description, workspace_path, is_active, created_at, updated_at
                FROM projects
                WHERE is_active = true
                ORDER BY slug
                """
            )
        return [ProjectListItem(**dict(r)) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/register", dependencies=[Depends(verify_api_key)])
async def register_project(body: RegisterProjectRequest):
    """
    Регистрация проекта в реестре (таблица projects).
    После регистрации Victoria и Veronica принимают запросы с project_context=body.slug.
    Защита: X-API-Key (тот же API_KEY, что для log_interaction, board/consult).
    """
    slug = (body.slug or "").strip().lower()
    if not slug or not slug.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="slug must be non-empty alphanumeric (hyphens/underscores allowed)")
    name = (body.name or slug)[:500]
    description = (body.description or "")[:5000] if body.description else None
    workspace_path = (body.workspace_path or f"/workspace/{slug}")[:1000] if body.workspace_path else f"/workspace/{slug}"
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO projects (slug, name, description, workspace_path, is_active)
                VALUES ($1, $2, $3, $4, true)
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    workspace_path = EXCLUDED.workspace_path,
                    updated_at = CURRENT_TIMESTAMP
                """,
                slug,
                name,
                description,
                workspace_path,
            )
        return {"ok": True, "slug": slug, "message": "Project registered. Restart Victoria/Veronica to pick up (or use TTL cache)."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/board/consult", response_model=BoardConsultResponse, dependencies=[Depends(verify_api_key)])
async def board_consult(body: BoardConsultRequest):
    """
    Консультация Совета Директоров по стратегическому вопросу.
    
    Вызывается backend'ом при обнаружении стратегического вопроса в чате.
    Совет анализирует контекст (OKR, задачи, знания) и выдаёт структурированное решение.
    """
    import logging
    import uuid
    _log = logging.getLogger(__name__)
    
    # Генерируем correlation_id если не передан
    correlation_id = body.correlation_id or str(uuid.uuid4())
    
    _log.info(f"[BOARD_CONSULT] question='{body.question[:100]}...' correlation_id={correlation_id}")
    
    try:
        from strategic_board import consult_board
        
        result = await consult_board(
            question=body.question,
            context=None,  # Контекст собирается внутри consult_board
            correlation_id=correlation_id,
            source=(body.source or "api"),
            session_id=body.session_id,
            user_id=body.user_id,
        )
        
        if result is None:
            _log.error(f"[BOARD_CONSULT] consult_board returned None for correlation_id={correlation_id}")
            raise HTTPException(
                status_code=503,
                detail="Board of Directors could not process the request. LLM may be unavailable."
            )
        
        _log.info(f"[BOARD_CONSULT] success correlation_id={correlation_id} decision='{result['structured_decision'].get('decision', '')[:50]}...'")
        
        return BoardConsultResponse(
            directive_text=result["directive_text"],
            structured_decision=result["structured_decision"],
            risk_level=result.get("risk_level"),
            recommend_human_review=result.get("recommend_human_review", False),
            correlation_id=correlation_id
        )
    
    except ImportError as e:
        _log.exception(f"[BOARD_CONSULT] ImportError: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"strategic_board module not available: {str(e)}"
        )
    except Exception as e:
        _log.exception(f"[BOARD_CONSULT] exception: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Board consult error: {str(e)}"
        )


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
        pool = await _get_db()
        async with pool.acquire() as conn:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/knowledge/{knowledge_id}", response_model=KnowledgeNodeResponse, dependencies=[Depends(verify_jwt_token)])
async def get_knowledge(knowledge_id: str):
    """Получение знания по ID"""
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", dependencies=[Depends(verify_jwt_token)])
async def search_knowledge(request: SearchRequest):
    """Поиск знаний"""
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
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
        pool = await _get_db()
        async with pool.acquire() as conn:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/reset-stuck")
async def reset_stuck_tasks(hours: int = 1):
    """
    Вернуть зависшие задачи (in_progress > N часов) обратно в pending.
    Нормально одновременно обрабатывается ~10 задач. Много «в работе» = зависли.
    
    hours: считать зависшими задачи в in_progress дольше N часов (по умолчанию 1)
    """
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE tasks 
                SET status = 'pending', updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('stuck_reset', true, 'previous_status', 'in_progress')
                WHERE status = 'in_progress' 
                  AND updated_at < NOW() - make_interval(hours => $1)
            """, hours)
            count = int(result.split()[-1]) if result and result.startswith("UPDATE") else 0
            return {"status": "success", "reset_count": count, "message": f"Вернуто в очередь: {count} зависших задач"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/reset-deferred")
async def reset_deferred_to_pending(limit: int = 100):
    """
    Вернуть задачи из deferred_to_human (ручная обработка) обратно в pending для повторной попытки.
    
    Используйте когда задачи ушли в ручную обработку из-за блокировки security/anomaly,
    но проблема уже исправлена.
    
    limit: максимум задач для сброса (по умолчанию 100)
    """
    try:
        pool = await _get_db()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                WITH to_reset AS (
                    SELECT id FROM tasks 
                    WHERE status = 'completed' AND metadata->>'deferred_to_human' = 'true' 
                    LIMIT $1
                )
                UPDATE tasks 
                SET status = 'pending', 
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) - 'deferred_to_human' - 'attempt_count' - 'last_attempt_failed' - 'last_error' - 'next_retry_after'
                WHERE id IN (SELECT id FROM to_reset)
            """, limit)
            # parse "UPDATE N" from result
            count = int(result.split()[-1]) if result and result.startswith("UPDATE") else 0
            return {
                "status": "success",
                "reset_count": count,
                "message": f"Вернуто в очередь: {count} задач. Worker подхватит их при следующем цикле."
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

