from sqlalchemy import String, Integer, Float, ForeignKey, Date, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    department: Mapped[str] = mapped_column(String(80), default="Open University Learning Analytics")
    roll_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    semester: Mapped[int] = mapped_column(Integer, default=1)
    oulad_student_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("code_module", "code_presentation", name="uq_subject_offering"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    code_module: Mapped[str] = mapped_column(String(10), index=True)
    code_presentation: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(120))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    semester: Mapped[int] = mapped_column(Integer, default=1)
    teacher = relationship("User")

class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("student_id", "subject_id", name="uq_student_subject_registration"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    date_registration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_unregistration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    highest_education: Mapped[str | None] = mapped_column(String(100), nullable=True)
    age_band: Mapped[str | None] = mapped_column(String(30), nullable=True)
    disability: Mapped[str | None] = mapped_column(String(10), nullable=True)
    studied_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_of_prev_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imd_band: Mapped[str | None] = mapped_column(String(30), nullable=True)
    final_result: Mapped[str | None] = mapped_column(String(30), nullable=True)
    student = relationship("User")
    subject = relationship("Subject")

class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    oulad_assessment_id: Mapped[int] = mapped_column(Integer, index=True)
    assessment_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    date: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=0)
    subject = relationship("Subject")

class AssessmentResult(Base):
    __tablename__ = "assessment_results"
    __table_args__ = (UniqueConstraint("student_id", "assessment_id", name="uq_student_assessment"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    student = relationship("User")
    assessment = relationship("Assessment")

class Engagement(Base):
    __tablename__ = "engagement"
    __table_args__ = (UniqueConstraint("student_id", "subject_id", name="uq_student_subject_engagement"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    total_clicks: Mapped[int] = mapped_column(Integer, default=0)
    active_days: Mapped[int] = mapped_column(Integer, default=0)
    student = relationship("User")
    subject = relationship("Subject")

class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    class_date: Mapped[object] = mapped_column(Date)
    present: Mapped[bool] = mapped_column(Boolean)

class ClassSession(Base):
    __tablename__ = "class_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    day: Mapped[str] = mapped_column(String(20))
    start_time: Mapped[str] = mapped_column(String(10))
    end_time: Mapped[str] = mapped_column(String(10))
    room: Mapped[str] = mapped_column(String(30))
