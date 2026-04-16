from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Item(Base):
    __tablename__ = "Item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="课堂名")
    class_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="授课班级")
    teacher: Mapped[str] = mapped_column(String(255), nullable=False, comment="授课教师")
    student_num: Mapped[int] = mapped_column(Integer, nullable=False, comment="这节课学生参与数")
    student_score_sum: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="这节课学生总分"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, comment="创建时间"
    )


class ItemStudent(Base):
    __tablename__ = "Student_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="班级名")
    student_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="姓名")
    sex: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="性别")
    item_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="参加的课堂id")
    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="总分")
    detail_score: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="细分得分")
    student_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="座位序号")
    row_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排")
    column_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="列")
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, default="#2f6bff", comment="颜色")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, comment="创建时间"
    )
