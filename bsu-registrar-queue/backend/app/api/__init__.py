from .router import router
from .queues import router as queues_router
from .tickets import router as tickets_router
from .students import router as students_router
from .auth import router as auth_router

__all__ = ["router"]