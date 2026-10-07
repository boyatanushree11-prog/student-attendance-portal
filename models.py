from sqlalchemy import Column, Integer, String, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    roll_no = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    student_class = Column(String, nullable=False)

    attendance_records = relationship("Attendance", back_populates="student")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String, nullable=False)  # Present, Absent, Late

    student = relationship("Student", back_populates="attendance_records")

    __table_args__ = (
        UniqueConstraint('student_id', 'date', name='_student_date_uc'),
    )