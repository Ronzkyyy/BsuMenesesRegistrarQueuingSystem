"""
SQLAlchemy database models - for actual database tables
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text, Date, Time
from datetime import time
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .core.database import Base
import enum


class QueueDBStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class QueueDBType(str, enum.Enum):
    ENROLLMENT = "enrollment"
    DOCUMENT_REQUEST = "document_request"
    CLEARANCE = "clearance"
    SCHOLARSHIP = "scholarship"
    OTHERS = "others"
    ADDING_DROPPING = "adding_dropping"
    PETITION_CLASS = "petition_class"
    OTHER_CONCERNS = "other_concerns"


class QueueDB(Base):
    __tablename__ = "queues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    queue_type = Column(Enum(QueueDBType), nullable=False)
    ticket_letter = Column(String(1), nullable=False)
    description = Column(Text)
    status = Column(Enum(QueueDBStatus), default=QueueDBStatus.ACTIVE)
    allow_priority = Column(Boolean, default=True)
    max_capacity = Column(Integer, default=50)
    slot_duration_minutes = Column(Integer, default=30)
    booking_enabled = Column(Boolean, default=False, nullable=False)
    operating_start_time = Column(Time, default=time(8, 0), nullable=False)
    operating_end_time = Column(Time, default=time(17, 0), nullable=False)
    slot_capacity = Column(Integer, default=3, nullable=False)
    booking_window_days = Column(Integer, default=14, nullable=False)
    current_ticket_number = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tickets = relationship("TicketDB", back_populates="queue")


class StudentDBType(str, enum.Enum):
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    ALUMNI = "alumni"


class Course(str, enum.Enum):
    BSIT = "Bachelor of Science in Information Technology"
    BSHM = "Bachelor of Science in Hospitality Management"
    BSBA = "Bachelor of Science in Business Administration"
    BIT = "Bachelor of Industrial Technology"


class Major(str, enum.Enum):
    COMPUTER_TECHNOLOGY = "BIT Computer Technology"
    FOOD_PROCESSING_TECHNOLOGY = "Food Processing Technology"


class YearLevel(str, enum.Enum):
    FIRST = "1st_year"
    SECOND = "2nd_year"
    THIRD = "3rd_year"
    FOURTH = "4th_year"
    FIFTH = "5th_year"
    GRADUATE = "graduate"


class StudentDB(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(10), unique=True, index=True, nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100))
    student_type = Column(Enum(StudentDBType), nullable=False)
    course = Column(Enum(Course), nullable=False)
    major = Column(Enum(Major), nullable=True)
    year_level = Column(Enum(YearLevel), nullable=False)
    is_scholar = Column(Boolean, default=False)
    is_varsity = Column(Boolean, default=False)
    is_graduating = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tickets = relationship("TicketDB", back_populates="student")


class TicketDBStatus(str, enum.Enum):
    WAITING = "waiting"
    SERVING = "serving"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class PriorityLevel(str, enum.Enum):
    NORMAL = "normal"
    PRIORITY = "priority"
    URGENT = "urgent"


class TicketDB(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(Integer, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    queue_id = Column(Integer, ForeignKey("queues.id"), nullable=False)
    priority = Column(Enum(PriorityLevel), default=PriorityLevel.NORMAL)
    purpose = Column(Text)
    status = Column(Enum(TicketDBStatus), default=TicketDBStatus.WAITING)
    position = Column(Integer)
    estimated_wait_time_minutes = Column(Integer)
    served_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    called_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("StudentDB", back_populates="tickets")
    queue = relationship("QueueDB", back_populates="tickets")


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    REGISTRAR = "registrar"
    STAFF = "staff"


class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MediaDBType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


class MediaDBSource(str, enum.Enum):
    UPLOAD = "upload"
    LINK = "link"


class MediaItemDB(Base):
    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True, index=True)
    media_type = Column(Enum(MediaDBType), nullable=False)
    url = Column(String, nullable=False)
    source = Column(Enum(MediaDBSource), default=MediaDBSource.LINK, nullable=False)
    display_duration_seconds = Column(Integer, default=10)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AnnouncementDB(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AppointmentDBStatus(str, enum.Enum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AppointmentDB(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    reference_code = Column(String(20), unique=True, index=True, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    queue_id = Column(Integer, ForeignKey("queues.id"), nullable=False)
    appointment_date = Column(Date, nullable=False)
    slot_start_time = Column(Time, nullable=False)
    slot_end_time = Column(Time, nullable=False)
    purpose = Column(Text)
    qr_token = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(Enum(AppointmentDBStatus), default=AppointmentDBStatus.BOOKED, nullable=False)
    checked_in_at = Column(DateTime(timezone=True))
    checked_in_by = Column(Integer, ForeignKey("users.id"))
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("StudentDB")
    queue = relationship("QueueDB")