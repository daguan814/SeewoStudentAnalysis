from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SeatPreview(BaseModel):
    student_number: int
    row_number: int
    column_number: int
    score: int
    color_hex: str


class ImagePreviewResponse(BaseModel):
    student_count: int
    score_min: int
    score_max: int
    seats: list[SeatPreview]


class ClassroomImportForm(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=255)
    class_name: str = Field(..., min_length=3, max_length=50)
    teacher: str = Field(..., min_length=1, max_length=100)
    student_lines_text: str = ""

    @field_validator("class_name")
    @classmethod
    def validate_class_name(cls, value: str) -> str:
        parts = value.split("-")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("授课班级格式必须是 年级-班级，例如 4-1")
        return value


class StudentImportResult(BaseModel):
    student_number: int
    row_number: int
    column_number: int
    student_name: str
    gender: str
    color_hex: str
    total_score: int
    detail_scores: list[int]


class ClassroomImportResponse(BaseModel):
    item_id: int
    student_count: int
    student_score_sum: int
    students: list[StudentImportResult]


class ItemListEntry(BaseModel):
    id: int
    item_name: str
    class_name: str
    teacher: str
    student_num: int
    student_score_sum: int
    created_at: str


class ItemListResponse(BaseModel):
    sort_by: str
    sort_order: str
    items: list[ItemListEntry]


class ItemStudentDetail(BaseModel):
    id: int
    student_number: int
    row_number: int
    column_number: int
    student_name: str
    sex: str
    color_hex: str
    score: int
    detail_score: str
    created_at: str


class ItemDetailResponse(BaseModel):
    id: int
    item_name: str
    class_name: str
    teacher: str
    student_num: int
    student_score_sum: int
    created_at: str
    sort_by: str
    sort_order: str
    students: list[ItemStudentDetail]
