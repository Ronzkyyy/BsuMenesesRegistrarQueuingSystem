"""
Student model for BSU student records
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class StudentType(str, Enum):
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    ALUMNI = "alumni"


class Course(str, Enum):
    BSIT = "Bachelor of Science in Information Technology"
    BSHM = "Bachelor of Science in Hospitality Management"
    BSBA = "Bachelor of Science in Business Administration"
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
    student_id: str = Field(..., pattern=r"^\d{10}$", description="10-digit student number, e.g. 2020201163")
    first_name: str
    last_name: str
    email: str
    student_type: StudentType
    course: Course
    major: Optional[Major] = None
    year_level: YearLevel
    is_scholar: bool = False
    is_varsity: bool = False
    is_graduating: bool = False

    @model_validator(mode="after")
    def validate_major(self) -> "StudentBase":
        if self.course == Course.BIT and self.major is None:
            raise ValueError("major is required for Bachelor of Industrial Technology")
        if self.course != Course.BIT and self.major is not None:
            raise ValueError("major is only applicable to Bachelor of Industrial Technology")
        return self


class StudentCreate(StudentBase):
    pass


class Student(StudentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StudentInDB(Student):
    id: int

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"