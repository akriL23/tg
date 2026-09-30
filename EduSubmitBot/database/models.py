from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class UserRole(Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"

class MemberRole(Enum):
    TEACHER = "teacher"
    STUDENT = "student"

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    full_name = Column(String)
    username = Column(String)
    role = Column(Enum(UserRole), default=UserRole.STUDENT)
    timezone = Column(String, default='UTC')
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    invite_code = Column(String, unique=True, index=True)
    teacher_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class GroupMember(Base):
    __tablename__ = 'group_members'
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey('groups.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    role = Column(Enum(MemberRole))

class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey('groups.id'))
    title = Column(String)
    description = Column(Text)
    file_id = Column(String, nullable=True)  # Telegram file_id
    deadline = Column(DateTime)
    allow_late = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Submission(Base):
    __tablename__ = 'submissions'
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey('assignments.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_late = Column(Boolean, default=False)
    status = Column(String, default='submitted')  # submitted, accepted, needs_rework, rejected
    teacher_comment = Column(Text, nullable=True)

class SubmissionFile(Base):
    __tablename__ = 'submission_files'
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'))
    file_id = Column(String)  # Telegram file_id
    file_name = Column(String)
    file_size = Column(Integer)
    version = Column(Integer, default=1)

class Reminder(Base):
    __tablename__ = 'reminders'
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey('assignments.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    remind_at = Column(DateTime)
    sent = Column(Boolean, default=False)