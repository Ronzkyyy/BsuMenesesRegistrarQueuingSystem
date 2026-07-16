"""
Student management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from ..core.database import get_db
from ..core.security import get_current_active_user, require_role
from ..db_models import UserRole, Course, YearLevel, StudentDBType
from ..models.student import Student, StudentCreate, StudentBase
from ..models.user import User
from ..services import StudentService


router = APIRouter()


@router.post("", response_model=Student)
def create_student(
    student: StudentCreate,
    db: Session = Depends(get_db)
):
    """Register a new student (public endpoint - students self-register at the kiosk before taking a ticket)"""
    service = StudentService(db)
    try:
        return service.create_student(student)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=Student)
def search_student(
    student_id: str = Query(..., description="10-digit student number (e.g., 2021000001)"),
    db: Session = Depends(get_db)
):
    """Search student by student ID number (public endpoint - used by the kiosk ticket flow)"""
    service = StudentService(db)
    student = service.get_student_by_student_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.get("/{student_id}", response_model=Student)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get student by internal ID"""
    service = StudentService(db)
    student = service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.get("", response_model=List[Student])
def list_students(
    query: str = "",
    course: Optional[Course] = None,
    year_level: Optional[YearLevel] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """List students with filters (staff only)"""
    service = StudentService(db)
    return service.search_students(
        query=query,
        course=course,
        year_level=year_level,
        skip=skip,
        limit=limit
    )


@router.patch("/{student_id}", response_model=Student)
def update_student(
    student_id: int,
    student_data: StudentBase,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Update student information (admin/registrar only)"""
    service = StudentService(db)
    student = service.update_student(student_id, student_data)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Delete a student (admin only)"""
    service = StudentService(db)
    if not service.delete_student(student_id):
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}


@router.get("/stats/summary")
def get_student_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Get student statistics"""
    service = StudentService(db)
    return service.get_student_stats()


@router.post("/bulk-import")
def bulk_import_students(
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

    return {
        "imported": len(results),
        "errors": len(errors),
        "results": results,
        "errors_detail": errors
    }