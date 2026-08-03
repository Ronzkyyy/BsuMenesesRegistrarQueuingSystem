"""
Student service - business logic for student management
"""
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
from sqlalchemy import func, or_

from ..db_models import (
    StudentDB, StudentDBType, Course, Major, YearLevel
)
from ..models.student import Student, StudentCreate, StudentBase


class StudentService:
    def __init__(self, db: Session):
        self.db = db

    def create_student(self, student_data: StudentCreate) -> Student:
        """Register a new student"""
        # Check if student_id already exists
        existing = self.db.query(StudentDB).filter(
            StudentDB.student_id == student_data.student_id
        ).first()
        if existing:
            raise ValueError(f"Student with ID {student_data.student_id} already exists")

        db_student = StudentDB(
            student_id=student_data.student_id,
            first_name=student_data.first_name,
            last_name=student_data.last_name,
            email=student_data.email,
            student_type=StudentDBType(student_data.student_type.value),
            course=Course(student_data.course.value),
            major=Major(student_data.major.value) if student_data.major else None,
            year_level=YearLevel(student_data.year_level.value),
            is_scholar=student_data.is_scholar,
            is_varsity=student_data.is_varsity,
            is_graduating=student_data.is_graduating,
        )
        self.db.add(db_student)
        self.db.commit()
        self.db.refresh(db_student)
        return self._to_student(db_student)

    def get_student_by_id(self, student_id: int) -> Optional[Student]:
        """Get student by internal ID"""
        student = self.db.query(StudentDB).filter(StudentDB.id == student_id).first()
        return self._to_student(student) if student else None

    def get_student_by_student_id(self, student_id: str) -> Optional[Student]:
        """Get student by student ID number"""
        student = self.db.query(StudentDB).filter(
            StudentDB.student_id == student_id
        ).first()
        return self._to_student(student) if student else None

    def search_students(
        self,
        query: str = "",
        course: Optional[Course] = None,
        year_level: Optional[YearLevel] = None,
        skip: int = 0,
        limit: int = 25
    ) -> Tuple[List[Student], int]:
        """Search students with filters. Returns (page of students, total matching count)."""
        q = self.db.query(StudentDB)

        if query:
            q = q.filter(
                or_(
                    StudentDB.student_id.ilike(f"%{query}%"),
                    StudentDB.first_name.ilike(f"%{query}%"),
                    StudentDB.last_name.ilike(f"%{query}%"),
                    StudentDB.email.ilike(f"%{query}%"),
                )
            )

        if course:
            q = q.filter(StudentDB.course == course)

        if year_level:
            q = q.filter(StudentDB.year_level == year_level)

        total = q.count()
        students = q.order_by(StudentDB.id).offset(skip).limit(limit).all()
        return [self._to_student(s) for s in students], total

    def update_student(self, student_id: int, student_data: StudentBase) -> Optional[Student]:
        """Update student information"""
        student = self.db.query(StudentDB).filter(StudentDB.id == student_id).first()
        if not student:
            return None

        student.first_name = student_data.first_name
        student.last_name = student_data.last_name
        student.email = student_data.email
        student.student_type = StudentDBType(student_data.student_type.value)
        student.course = Course(student_data.course.value)
        student.major = Major(student_data.major.value) if student_data.major else None
        student.year_level = YearLevel(student_data.year_level.value)
        student.is_scholar = student_data.is_scholar
        student.is_varsity = student_data.is_varsity
        student.is_graduating = student_data.is_graduating

        self.db.commit()
        self.db.refresh(student)
        return self._to_student(student)

    def delete_student(self, student_id: int) -> bool:
        """Delete a student. Returns False if the student doesn't exist.

        Raises ValueError if the student has any tickets (even completed/old
        ones) - deleting them would violate the tickets.student_id foreign
        key and silently destroy historical ticket records, so we block it
        with a clear message instead of letting the database raise a raw 500.
        """
        from ..db_models import TicketDB

        student = self.db.query(StudentDB).filter(StudentDB.id == student_id).first()
        if not student:
            return False

        ticket_count = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.student_id == student_id
        ).scalar()
        if ticket_count:
            raise ValueError(
                f"Cannot delete student '{student.student_id}': they have {ticket_count} ticket(s) "
                f"on record."
            )

        self.db.delete(student)
        self.db.commit()
        return True

    def get_student_stats(self) -> dict:
        """Get student statistics"""
        total = self.db.query(func.count(StudentDB.id)).scalar()

        by_course = self.db.query(
            StudentDB.course, func.count(StudentDB.id)
        ).group_by(StudentDB.course).all()

        by_year = self.db.query(
            StudentDB.year_level, func.count(StudentDB.id)
        ).group_by(StudentDB.year_level).all()

        by_type = self.db.query(
            StudentDB.student_type, func.count(StudentDB.id)
        ).group_by(StudentDB.student_type).all()

        scholars = self.db.query(func.count(StudentDB.id)).filter(
            StudentDB.is_scholar == True
        ).scalar()

        varsity = self.db.query(func.count(StudentDB.id)).filter(
            StudentDB.is_varsity == True
        ).scalar()

        graduating = self.db.query(func.count(StudentDB.id)).filter(
            StudentDB.is_graduating == True
        ).scalar()

        return {
            "total_students": total,
            "scholars": scholars,
            "varsity": varsity,
            "graduating": graduating,
            "by_course": {c.value: count for c, count in by_course},
            "by_year_level": {y.value: count for y, count in by_year},
            "by_type": {t.value: count for t, count in by_type},
        }

    def _to_student(self, db_student: StudentDB) -> Student:
        """Convert DB model to Pydantic model"""
        return Student(
            id=db_student.id,
            student_id=db_student.student_id,
            first_name=db_student.first_name,
            last_name=db_student.last_name,
            email=db_student.email,
            student_type=StudentDBType(db_student.student_type.value),
            course=Course(db_student.course.value),
            major=Major(db_student.major.value) if db_student.major else None,
            year_level=YearLevel(db_student.year_level.value),
            is_scholar=db_student.is_scholar,
            is_varsity=db_student.is_varsity,
            is_graduating=db_student.is_graduating,
            created_at=db_student.created_at,
            updated_at=db_student.updated_at,
        )