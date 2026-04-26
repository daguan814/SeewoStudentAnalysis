from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.heatmap_detector import HeatmapDetectionError
from app.migrations import ensure_existing_schema
from app.schemas import (
    ClassroomImportForm,
    ClassroomImportResponse,
    ImagePreviewResponse,
    ItemDetailResponse,
    ItemListEntry,
    ItemListResponse,
    ItemStudentDetail,
    ParentMessageResponse,
    ParentMessageUpdateRequest,
    SeatPreview,
    StudentCommentaryResponse,
    StudentMetric,
    StudentProfileResponse,
    StudentImportResult,
)
from app.services import (
    detect_seats_from_upload,
    generate_student_commentary,
    get_student_profile,
    get_item_detail,
    import_classroom_from_detection,
    list_items,
    update_parent_message,
)


def load_local_env() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    for env_path in (root_dir / ".env", Path(__file__).resolve().parent / ".env"):
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_local_env()
ensure_existing_schema(engine)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Seewo Student Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/classroom-image/preview", response_model=ImagePreviewResponse)
def preview_classroom_image(image: UploadFile = File(...)):
    try:
        _saved_path, result = detect_seats_from_upload(image)
    except HeatmapDetectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ordered = sorted(result.seats, key=lambda seat: seat.seat_number)
    return ImagePreviewResponse(
        student_count=result.seat_count,
        score_min=result.score_min,
        score_max=result.score_max,
        seats=[
            SeatPreview(
                student_number=seat.seat_number,
                row_number=seat.row_number,
                column_number=seat.column_number,
                score=seat.score,
                color_hex=seat.color_hex,
            )
            for seat in ordered
        ],
    )


@app.post("/api/classroom-image/import", response_model=ClassroomImportResponse)
def import_classroom_image(
    image: UploadFile = File(...),
    item_name: str = Form(...),
    class_name: str = Form(...),
    teacher: str = Form(...),
    student_lines_text: str = Form(""),
    db: Session = Depends(get_db),
):
    payload = ClassroomImportForm(
        item_name=item_name,
        class_name=class_name,
        teacher=teacher,
        student_lines_text=student_lines_text,
    )

    try:
        _saved_path, result = detect_seats_from_upload(image)
        item, students = import_classroom_from_detection(db, payload, result)
    except HeatmapDetectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ClassroomImportResponse(
        item_id=item.id,
        student_count=item.student_num,
        student_score_sum=item.student_score_sum,
        students=[StudentImportResult(**student) for student in students],
    )


@app.get("/api/items", response_model=ItemListResponse)
def fetch_items(
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    items = list_items(db, sort_by=sort_by, sort_order=sort_order)
    return ItemListResponse(
        sort_by=sort_by,
        sort_order=sort_order,
        items=[
            ItemListEntry(
                id=item.id,
                item_name=item.item_name,
                class_name=item.class_name,
                teacher=item.teacher,
                student_num=item.student_num,
                student_score_sum=item.student_score_sum,
                created_at=item.created_at.isoformat(sep=" ", timespec="seconds"),
            )
            for item in items
        ],
    )


@app.get("/api/items/{item_id}", response_model=ItemDetailResponse)
def fetch_item_detail(
    item_id: int,
    sort_by: str = "student_number",
    sort_order: str = "asc",
    db: Session = Depends(get_db),
):
    item, students = get_item_detail(db, item_id=item_id, sort_by=sort_by, sort_order=sort_order)
    if item is None:
        raise HTTPException(status_code=404, detail="没有找到这节课。")

    return ItemDetailResponse(
        id=item.id,
        item_name=item.item_name,
        class_name=item.class_name,
        teacher=item.teacher,
        student_num=item.student_num,
        student_score_sum=item.student_score_sum,
        created_at=item.created_at.isoformat(sep=" ", timespec="seconds"),
        sort_by=sort_by,
        sort_order=sort_order,
        students=[
            ItemStudentDetail(
                id=student.id,
                student_number=student.student_number,
                row_number=student.row_number,
                column_number=student.column_number,
                student_name=student.student_name,
                sex=student.sex,
                color_hex=student.color_hex,
                score=student.score,
                detail_score=student.detail_score,
                created_at=student.created_at.isoformat(sep=" ", timespec="seconds"),
            )
            for student in students
        ],
    )


@app.get("/api/items/{item_id}/students/{student_id}", response_model=StudentProfileResponse)
def fetch_student_profile(
    item_id: int,
    student_id: int,
    db: Session = Depends(get_db),
):
    item, student, metrics = get_student_profile(db, item_id=item_id, student_id=student_id)
    if item is None:
        raise HTTPException(status_code=404, detail="没有找到这节课。")
    if student is None:
        raise HTTPException(status_code=404, detail="没有找到这个学生。")

    return StudentProfileResponse(
        id=student.id,
        item_id=item.id,
        item_name=item.item_name,
        class_name=item.class_name,
        teacher=item.teacher,
        student_name=student.student_name,
        sex=student.sex,
        student_number=student.student_number,
        row_number=student.row_number,
        column_number=student.column_number,
        score=student.score,
        color_hex=student.color_hex,
        parent_message=student.parent_message,
        metrics=[StudentMetric(**metric) for metric in metrics],
    )


@app.post(
    "/api/items/{item_id}/students/{student_id}/parent-message",
    response_model=ParentMessageResponse,
)
def save_parent_message(
    item_id: int,
    student_id: int,
    payload: ParentMessageUpdateRequest,
    db: Session = Depends(get_db),
):
    item, student = update_parent_message(
        db,
        item_id=item_id,
        student_id=student_id,
        parent_message=payload.parent_message,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="没有找到这节课。")
    if student is None:
        raise HTTPException(status_code=404, detail="没有找到这个学生。")

    return ParentMessageResponse(parent_message=student.parent_message)


@app.post(
    "/api/items/{item_id}/students/{student_id}/commentary",
    response_model=StudentCommentaryResponse,
)
def fetch_student_commentary(
    item_id: int,
    student_id: int,
    db: Session = Depends(get_db),
):
    item, student, metrics = get_student_profile(db, item_id=item_id, student_id=student_id)
    if item is None:
        raise HTTPException(status_code=404, detail="没有找到这节课。")
    if student is None:
        raise HTTPException(status_code=404, detail="没有找到这个学生。")

    try:
        commentary = generate_student_commentary(item, student, metrics)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return StudentCommentaryResponse(commentary=commentary)
