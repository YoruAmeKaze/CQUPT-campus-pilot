from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=func.now())

    # 关系
    data_sources = relationship("DataSource", back_populates="user", lazy="dynamic")
    courses = relationship("Course", back_populates="user", lazy="dynamic")
    assignments = relationship("Assignment", back_populates="user", lazy="dynamic")
    notifications = relationship("Notification", back_populates="user", lazy="dynamic")
    todos = relationship("Todo", back_populates="user", lazy="dynamic")


class DataSource(Base):
    """用户在 Web UI 中添加的数据源配置"""
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(20), nullable=False)  # "jwxt" | "chaoxing" | "smartestu"
    name = Column(String(100))  # 用户自定义名称
    enabled = Column(Boolean, default=True)
    credentials = Column(Text)  # Fernet 加密后的 JSON 字符串
    last_sync = Column(DateTime, nullable=True)
    sync_status = Column(String(20), default="pending")  # pending/ok/error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # 关系
    user = relationship("User", back_populates="data_sources")
    courses = relationship("Course", back_populates="source")
    assignments = relationship("Assignment", back_populates="source")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    name = Column(String(200), nullable=False)
    teacher = Column(String(100), nullable=True)
    location = Column(String(200), nullable=True)  # 默认/单地点（兼容旧数据）
    location_schedule = Column(Text, nullable=True)  # JSON: [{"start_week":1,"end_week":4,"location":"A101"},...]
    day_of_week = Column(Integer)  # 1=周一 … 7=周日
    start_week = Column(Integer)
    end_week = Column(Integer)
    week_mask = Column(String(30))  # 周次二进制标记，如 '111101111111110000000'
    start_slot = Column(Integer)  # 第几节开始
    end_slot = Column(Integer)
    start_time = Column(String(10))  # "08:30"
    end_time = Column(String(10))  # "10:05"
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关系
    user = relationship("User", back_populates="courses")
    source = relationship("DataSource", back_populates="courses")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    remote_id = Column(String(100), nullable=True)  # 平台原始 ID，用于去重
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    course_name = Column(String(200), nullable=True)
    due_time = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 推送状态
    notified_new = Column(Boolean, default=False)
    notified_24h = Column(Boolean, default=False)
    notified_1h = Column(Boolean, default=False)

    # 关系
    user = relationship("User", back_populates="assignments")
    source = relationship("DataSource", back_populates="assignments")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(
        String(50),
        nullable=False,
    )  # "new_assignment"|"deadline_24h"|"deadline_1h"|"daily_summary"
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=func.now())
    success = Column(Boolean, default=True)

    # 关系
    user = relationship("User", back_populates="notifications")


class Todo(Base):
    """待办事项"""
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    due_time = Column(DateTime, nullable=True)
    priority = Column(String(20), default="normal")  # "low" / "normal" / "high"
    is_completed = Column(Boolean, default=False)
    source = Column(String(50), default="manual")  # "manual" / "llm"
    reminder_enabled = Column(Boolean, default=False)  # 是否开启提醒
    reminder_sent = Column(Boolean, default=False)  # 提醒是否已发送
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关系
    user = relationship("User", back_populates="todos")


class SystemConfig(Base):
    """系统配置键值存储（替代 .env 中的业务配置）"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(String(200), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class RoomSchedule(Base):
    """教室课表/空教室数据"""
    __tablename__ = "room_schedules"

    id = Column(Integer, primary_key=True, index=True)
    room_name = Column(String(100), nullable=False, index=True)  # 教室名，如 "3105"
    room_type = Column(String(50), default="教室")  # 教室 / 实验室 / 室外
    capacity = Column(Integer, nullable=True)  # 可容纳人数
    building = Column(String(100), nullable=True)  # 所属教学楼
    day_of_week = Column(Integer, nullable=False)  # 1=周一 … 7=周日
    start_slot = Column(Integer, nullable=False)  # 开始节次
    end_slot = Column(Integer, nullable=False)  # 结束节次
    start_week = Column(Integer, nullable=False)  # 开始周
    end_week = Column(Integer, nullable=False)  # 结束周
    week_mask = Column(String(30), nullable=True)  # 周次二进制标记
    course_name = Column(String(200), nullable=True)  # 占用课程名（空则为空闲）
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CustomReminder(Base):
    """自定义定时提醒"""
    __tablename__ = "custom_reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False)  # 提醒名称（用户自定义）
    title = Column(String(200), nullable=False)  # 推送标题
    content = Column(Text, nullable=True)  # 推送内容
    repeat_type = Column(String(20), nullable=False, default="daily")  # daily / weekly / monthly
    repeat_day = Column(Integer, nullable=True)  # weekly=0-6(周一到周日), monthly=1-31
    reminder_time = Column(String(5), nullable=False)  # HH:MM 格式
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
