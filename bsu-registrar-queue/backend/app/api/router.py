"""
Main API router combining all endpoints
"""
from fastapi import APIRouter
from .queues import router as queues_router
from .tickets import router as tickets_router
from .students import router as students_router
from .auth import router as auth_router
from .media import router as media_router
from .announcements import router as announcements_router
from .appointments import router as appointments_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(queues_router, prefix="/queues", tags=["queues"])
router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
router.include_router(students_router, prefix="/students", tags=["students"])
router.include_router(media_router, prefix="/media", tags=["media"])
router.include_router(announcements_router, prefix="/announcements", tags=["announcements"])
router.include_router(appointments_router, prefix="/appointments", tags=["appointments"])
