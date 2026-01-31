"""
API Auto-Optimizer: статус, дашборд, управление.
"""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/auto-optimizer", tags=["auto-optimizer"])


def get_auto_optimizer(request: Request):
    """AutoOptimizer из app.state или создание нового (если не запущен)."""
    opt = getattr(request.app.state, "auto_optimizer", None)
    if opt is None:
        from app.services.optimization.auto_optimizer import AutoOptimizer
        opt = AutoOptimizer()
    return opt


@router.get("/status")
async def get_status(request: Request):
    """Статус Auto-Optimizer."""
    opt = get_auto_optimizer(request)
    return {
        "is_running": opt.is_running,
        "optimizations_count": len(opt.optimization_history),
    }


@router.get("/dashboard")
async def get_dashboard(request: Request):
    """Данные для дашборда."""
    opt = get_auto_optimizer(request)
    return opt.get_dashboard_data()
