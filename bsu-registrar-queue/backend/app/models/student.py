"""
Student model for BSU student records
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from enum import Enum


class StudentType(str, Enum):
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    ALUMNI = "alumni"


class Course(str, Enum):
    BSIT = "Bachelor of Science in Information Technology"
    BSHM = "Bachelor of Science in Hospitality Management"
    BSBA = "Bachelor of Science in Business Administration"
    BSCPE = "Bachelor of Science in Computer Engineering"
    BSED = "Bachelor of Science in Education"
    BIT = "Bachelor of Industrial Technology"


class Major(str, Enum):
    COMPUTER_TECHNOLOGY = "BIT Computer Technology"
    FOOD_PROCESSING_TECHNOLOGY = "Food Processing Technology"


class YearLevel(str, Enum):
    FIRST = "1st_year"
    SECOND = "2nd_year"
    THIRD = "3rd_year"
    FOURTH = "4th_year"
    FIFTH = "5th_year"
    GRADUATE = "graduate"


class StudentBase(BaseModel):
    """Identity/enrollment fields any caller may provide - deliberately excludes
    is_scholar/is_varsity/is_graduating. Those flags feed straight into
    TicketService.calculate_priority (is_graduating -> URGENT, the others ->
    PRIORITY), so they must never be settable by the public, unauthenticated
    kiosk self-registration endpoint (POST /students uses this model) - a
    self-declared "Graduating Student" checkbox would let anyone jump every
    queue. Only StudentCreate (below) - used by the registrar-gated PATCH and
    the admin-only file import - can set them."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    student_id: str = Field(..., pattern=r"^\d{10}$", description="10-digit student number, e.g. 2020201163")
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr = Field(..., max_length=100)
    student_type: StudentType
    course: Course
    major: Optional[Major] = None
    year_level: YearLevel

    @model_validator(mode="after")
    def validate_major(self) -> "StudentBase":
        if self.course == Course.BIT and self.major is None:
            raise ValueError("major is required for Bachelor of Industrial Technology")
        if self.course != Course.BIT and self.major is not None:
            raise ValueError("major is only applicable to Bachelor of Industrial Technology")
        return self


class StudentCreate(StudentBase):
    """For trusted (staff-authenticated) callers only - see StudentBase."""
    is_scholar: bool = False
    is_varsity: bool = False
    is_graduating: bool = False


class Student(StudentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class StudentInDB(Student):
    id: int

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class StudentPublic(BaseModel):
    """Minimal-disclosure shape for the unauthenticated kiosk lookup endpoint.

    The full Student model includes course/major/year_level and the
    is_scholar/is_varsity/is_graduating flags - none of that is needed to
    prefill the ticket-taking form, and it shouldn't be exposed to an
    anonymous caller who only supplied a guessable 10-digit student number.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    first_name: str
    last_name: str
    # Masked ("j***@gmail.com") - enough for a student to recognise their
    # address and spot a typo, not enough to harvest addresses by guessing
    # student numbers. Staff models keep the full address.
    email_masked: str

    @model_validator(mode="before")
    @classmethod
    def _mask_email(cls, data):
        # Built from a StudentDB row: derive email_masked from .email, and
        # never carry the full address into this public shape.
        from ..services.email_mask import mask_email
        if isinstance(data, dict):
            return {**{k: v for k, v in data.items() if k != "email"},
                    "email_masked": mask_email(data.get("email", ""))}
        return {
            "id": data.id, "student_id": data.student_id,
            "first_name": data.first_name, "last_name": data.last_name,
            "email_masked": mask_email(data.email or ""),
        }


class StudentListResponse(BaseModel):
    items: List[Student]
    total: int
    skip: int
    limit: int