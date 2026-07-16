"""
Main API router combining all endpoints
"""
from fastapi import APIRouter
from .queues import router as queues_router
from .tickets import router as tickets_router
from .students import router as students_router
from .auth import router as auth_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(queues_router, prefix="/queues", tags=["queues"])
router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
router.include_router(students_router, prefix="/students", tags=["students"])