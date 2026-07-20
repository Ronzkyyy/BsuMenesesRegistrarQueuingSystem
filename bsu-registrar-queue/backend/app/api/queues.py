"""
Queue management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..core.database import get_db
from ..core.security import get_current_active_user, require_role
from ..db_models import UserRole
from ..models.queue import Queue, QueueCreate, QueueStatus, QueueInDB
from ..models.user import User
from ..services import QueueService


router = APIRouter()


@router.post("", response_model=Queue)
def create_queue(
    queue: QueueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Create a new service queue (admin/registrar only)"""
    service = QueueService(db)
    try:
        return service.create_queue(queue)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[Queue])
def list_queues(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all queues"""
    service = QueueService(db)
    return service.get_all_queues(skip=skip, limit=limit)


@router.get("/active", response_model=List[Queue])
def list_active_queues(
    db: Session = Depends(get_db)
):
    """List all active queues (public endpoint for students)"""
    service = QueueService(db)
    return service.get_active_queues()


@router.get("/dashboard-summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Get aggregate stats for the admin dashboard overview"""
    service = QueueService(db)
    return service.get_dashboard_summary()


@router.get("/{queue_id}", response_model=Queue)
def get_queue(
    queue_id: int,
    db: Session = Depends(get_db)
):
    """Get specific queue (public endpoint - students view this before taking a ticket)"""
    service = QueueService(db)
    queue = service.get_queue_by_id(queue_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue


@router.patch("/{queue_id}/status", response_model=Queue)
def update_queue_status(
    queue_id: int,
    status: QueueStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Update queue status (admin/registrar only)"""
    service = QueueService(db)
    queue = service.update_queue_status(queue_id, status)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue


@router.post("/{queue_id}/pause", response_model=Queue)
def pause_queue(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Pause a queue - no new tickets allowed"""
    service = QueueService(db)
    queue = service.pause_queue(queue_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue


@router.post("/{queue_id}/resume", response_model=Queue)
def resume_queue(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Resume a paused queue"""
    service = QueueService(db)
    queue = service.resume_queue(queue_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue


@router.post("/{queue_id}/close", response_model=Queue)
def close_queue(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Close queue for the day"""
    service = QueueService(db)
    queue = service.close_queue(queue_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue


@router.get("/{queue_id}/stats")
def get_queue_stats(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Get queue statistics"""
    service = QueueService(db)
    stats = service.get_queue_stats(queue_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Queue not found")
    return stats


@router.delete("/{queue_id}")
def delete_queue(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Delete a queue (admin only)"""
    service = QueueService(db)
    try:
        deleted = service.delete_queue(queue_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Queue not found")

    return {"message": "Queue deleted successfully"}