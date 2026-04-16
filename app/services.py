from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.heatmap_detector import detect_heatmap
from app.models import Item, ItemStudent
from app.schemas import ClassroomImportForm


UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_upload_file(image: UploadFile) -> Path:
    suffix = Path(image.filename or "upload.png").suffix or ".png"
    destination = UPLOAD_DIR / f"heatmap_{random.randint(100000, 999999)}{suffix}"
    with destination.open("wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    return destination


def split_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line]


def normalize_people_inputs(student_lines_text: str, count: int) -> tuple[list[str], list[str]]:
    names: list[str] = []
    genders: list[str] = []

    for line in split_lines(student_lines_text):
        parts = [part for part in line.replace("\t", " ").split(" ") if part]
        if not parts:
            continue
        if len(parts) == 1:
            names.append(parts[0])
            genders.append("")
        else:
            names.append(parts[0])
            genders.append(parts[-1])

    while len(names) < count:
        names.append("")
    while len(genders) < count:
        genders.append("")

    return names[:count], genders[:count]


def generate_detail_scores(max_total: int) -> list[int]:
    if max_total <= 0:
        return [0, 0, 0, 0, 0, 0]

    min_total = max(20, int(max_total * 0.72))
    target_total = random.randint(min_total, max_total)
    base = target_total // 6
    scores = [base] * 6
    remainder = target_total - base * 6

    for index in range(remainder):
        scores[index] += 1

    for _ in range(24):
        giver = random.randrange(6)
        receiver = random.randrange(6)
        if giver == receiver or scores[giver] <= max(0, base - 2):
            continue
        if scores[receiver] >= base + 3:
            continue
        scores[giver] -= 1
        scores[receiver] += 1

    random.shuffle(scores)
    return scores


def assign_color_hex(students: list[dict]) -> None:
    palette = ["#2f6bff", "#35b56a", "#f3c64d", "#f08a32", "#d94b3d"]
    ordered = sorted(
        students,
        key=lambda student: (student["total_score"], student["student_number"]),
    )
    total = len(ordered)
    if total == 0:
        return

    for index, student in enumerate(ordered):
        ratio = 0 if total == 1 else index / (total - 1)
        bucket = min(4, int(ratio * 5))
        student["color_hex"] = palette[bucket]


def detect_seats_from_upload(image: UploadFile) -> tuple[Path, object]:
    saved_path = save_upload_file(image)
    result = detect_heatmap(str(saved_path))
    return saved_path, result


def import_classroom_from_detection(
    db: Session,
    payload: ClassroomImportForm,
    detection_result,
) -> tuple[Item, list[dict]]:
    ordered_seats = sorted(
        detection_result.seats,
        key=lambda seat: seat.seat_number,
    )
    names, genders = normalize_people_inputs(payload.student_lines_text, len(ordered_seats))

    students = []
    student_score_sum = 0

    for index, seat in enumerate(ordered_seats):
        total_score = int(seat.score)
        detail_scores = generate_detail_scores(total_score)
        student_score_sum += total_score
        students.append(
            {
                "student_number": int(seat.seat_number),
                "row_number": int(seat.row_number),
                "column_number": int(seat.column_number),
                "student_name": names[index],
                "gender": genders[index],
                "total_score": total_score,
                "detail_scores": detail_scores,
            }
        )

    assign_color_hex(students)

    item = Item(
        item_name=payload.item_name,
        class_name=payload.class_name,
        teacher=payload.teacher,
        student_num=len(students),
        student_score_sum=student_score_sum,
    )
    db.add(item)
    db.flush()

    for student in students:
        db.add(
            ItemStudent(
                class_name=payload.class_name,
                item_id=item.id,
                student_number=student["student_number"],
                row_number=student["row_number"],
                column_number=student["column_number"],
                student_name=student["student_name"],
                sex=student["gender"],
                score=student["total_score"],
                detail_score=json.dumps(student["detail_scores"], ensure_ascii=False),
                color_hex=student["color_hex"],
            )
        )

    db.commit()
    db.refresh(item)
    return item, students


ITEM_SORT_FIELDS = {
    "id": Item.id,
    "created_at": Item.created_at,
    "item_name": Item.item_name,
    "class_name": Item.class_name,
    "teacher": Item.teacher,
    "student_num": Item.student_num,
    "student_score_sum": Item.student_score_sum,
}

ITEM_STUDENT_SORT_FIELDS = {
    "student_number": ItemStudent.student_number,
    "row_number": ItemStudent.row_number,
    "column_number": ItemStudent.column_number,
    "student_name": ItemStudent.student_name,
    "sex": ItemStudent.sex,
    "score": ItemStudent.score,
    "created_at": ItemStudent.created_at,
}


def _build_order_clause(sort_by: str, sort_order: str, field_map: dict):
    column = field_map.get(sort_by) or next(iter(field_map.values()))
    if sort_order == "asc":
        return asc(column)
    return desc(column)


def list_items(db: Session, sort_by: str = "created_at", sort_order: str = "desc") -> list[Item]:
    stmt = select(Item).order_by(_build_order_clause(sort_by, sort_order, ITEM_SORT_FIELDS))
    return list(db.scalars(stmt).all())


def get_item_detail(
    db: Session, item_id: int, sort_by: str = "student_number", sort_order: str = "asc"
) -> tuple[Item | None, list[ItemStudent]]:
    item = db.get(Item, item_id)
    if item is None:
        return None, []

    stmt = (
        select(ItemStudent)
        .where(ItemStudent.item_id == item_id)
        .order_by(_build_order_clause(sort_by, sort_order, ITEM_STUDENT_SORT_FIELDS))
    )
    students = list(db.scalars(stmt).all())
    return item, students
