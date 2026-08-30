"""
Student management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional

from ..core.audit import log_security_event
from ..core.database import get_db
from ..core.limiter import limiter
from ..core.security import get_current_active_user, require_role
from ..db_models import UserRole, Course, YearLevel, StudentDBType
from ..models.student import Student, StudentCreate, StudentBase, StudentListResponse, StudentPublic
from ..models.user import User
from ..services import StudentService


router = APIRouter()


@router.post("", response_model=Student)
@limiter.limit("10/minute")
def create_student(
    request: Request,
    student: StudentCreate,
    db: Session = Depends(get_db)
):
    """Register a new student (public endpoint - students self-register at the kiosk before taking a ticket)"""
    service = StudentService(db)
    try:
        return service.create_student(student)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=StudentPublic)
@limiter.limit("20/minute")
def search_student(
    request: Request,
    student_id: str = Query(..., pattern=r"^\d{10}$", description="10-digit student number (e.g., 2021000001)"),
    db: Session = Depends(get_db)
):
    """Search student by student ID number (public endpoint - used by the kiosk ticket flow).

    Returns only the fields the kiosk UI actually needs (name/email to
    confirm identity before taking a ticket) - not course, year level, or
    the is_scholar/is_varsity/is_graduating flags, since this is reachable
    by anyone who can guess a 10-digit student number, with no login.
    """
    service = StudentService(db)
    student = service.get_student_by_student_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.get("/{student_id}", response_model=Student)
def get_student(
    student_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get student by internal ID"""
    service = StudentService(db)
    student = service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.get("", response_model=StudentListResponse)
def list_students(
    query: str = Query("", max_length=100),
    course: Optional[Course] = None,
    year_level: Optional[YearLevel] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STAFF))
):
    """List students with filters (staff only)"""
    service = StudentService(db)
    items, total = service.search_students(
        query=query,
        course=course,
        year_level=year_level,
        skip=skip,
        limit=limit
    )
    return StudentListResponse(items=items, total=total, skip=skip, limit=limit)


@router.patch("/{student_id}", response_model=Student)
def update_student(
    student_data: StudentBase,
    student_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """Update student information (admin/registrar only)"""
    service = StudentService(db)
    student = service.update_student(student_id, student_data)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.delete("/{student_id}")
def delete_student(
    request: Request,
    student_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Delete a student (admin only)"""
    service = StudentService(db)
    try:
        if not service.delete_student(student_id):
            raise HTTPException(status_code=404, detail="Student not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_security_event(
        "student.deleted", outcome="success", request=request,
        actor=current_user.username, target=f"student#{student_id}",
    )
    return {"message": "Student deleted successfully"}


@router.get("/stats/summary")
def get_student_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """Get student statistics"""
    service = StudentService(db)
    return service.get_student_stats()


@router.post("/bulk-import")
def bulk_import_students(
    request: Request,
    students: List[StudentCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Bulk import students (admin only)"""
    service = StudentService(db)
    results = []
    errors = []

    for i, student_data in enumerate(students):
        try:
            student = service.create_student(student_data)
            results.append(student)
        except ValueError as e:
            errors.append({"index": i, "error": str(e)})

    log_security_event(
        "student.bulk_imported", outcome="success", request=request,
        actor=current_user.username,
        detail=f"imported={len(results)} errors={len(errors)}",
    )
    return {
        "imported": len(results),
        "errors": len(errors),
        "results": results,
        "errors_detail": errors
    }