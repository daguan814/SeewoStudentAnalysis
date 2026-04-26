from __future__ import annotations

import json
import os
import random
import shutil
from pathlib import Path
from urllib import error, request

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
        return [0, 0, 0, 0, 0]

    min_total = max(20, int(max_total * 0.72))
    target_total = random.randint(min_total, max_total)
    base = target_total // 5
    scores = [base] * 5
    remainder = target_total - base * 5

    for index in range(remainder):
        scores[index] += 1

    for _ in range(20):
        giver = random.randrange(5)
        receiver = random.randrange(5)
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

STUDENT_METRIC_META = [
    {
        "key": "interest_red",
        "label": "兴趣培养",
        "description": "主动发言、勇敢提问、分享趣事。",
        "color_hex": "#e0564a",
    },
    {
        "key": "habit_yellow",
        "label": "习惯养成",
        "description": "认真倾听，专注课堂、书写工整、整理学具、不拖拉、帮助同伴。",
        "color_hex": "#f2bf43",
    },
    {
        "key": "thinking_blue",
        "label": "思维发展",
        "description": "独特解法、发展规律、创意表达。",
        "color_hex": "#356cf0",
    },
    {
        "key": "problem_green",
        "label": "问题解决",
        "description": "独力攻克难题，纠错反思。",
        "color_hex": "#32b368",
    },
    {
        "key": "value_purple",
        "label": "成果增值",
        "description": "作业进步，达成目标，成果优秀。",
        "color_hex": "#8a56e2",
    },
]

COLOR_NAME_MAP = {
    "#2f6bff": "思维发展",
    "#35b56a": "问题解决",
    "#f3c64d": "习惯养成",
    "#f08a32": "成果增值",
    "#d94b3d": "兴趣培养",
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


def parse_detail_scores(detail_score: str) -> list[int]:
    try:
        values = json.loads(detail_score or "[]")
    except json.JSONDecodeError:
        return [0, 0, 0, 0, 0]

    if not isinstance(values, list):
        return [0, 0, 0, 0, 0]

    normalized = []
    for value in values[:5]:
        try:
            normalized.append(max(0, min(100, int(value))))
        except (TypeError, ValueError):
            normalized.append(0)

    while len(normalized) < 5:
        normalized.append(0)
    return normalized


def get_student_profile(
    db: Session,
    item_id: int,
    student_id: int,
) -> tuple[Item | None, ItemStudent | None, list[dict]]:
    item = db.get(Item, item_id)
    if item is None:
        return None, None, []

    stmt = select(ItemStudent).where(
        ItemStudent.item_id == item_id,
        ItemStudent.id == student_id,
    )
    student = db.scalar(stmt)
    if student is None:
        return item, None, []

    scores = parse_detail_scores(student.detail_score)
    metrics = []
    for index, meta in enumerate(STUDENT_METRIC_META):
        metrics.append(
            {
                "key": meta["key"],
                "label": meta["label"],
                "description": meta["description"],
                "color_hex": meta["color_hex"],
                "score": scores[index],
            }
        )

    return item, student, metrics


def update_parent_message(
    db: Session,
    item_id: int,
    student_id: int,
    parent_message: str,
) -> tuple[Item | None, ItemStudent | None]:
    item = db.get(Item, item_id)
    if item is None:
        return None, None

    stmt = select(ItemStudent).where(
        ItemStudent.item_id == item_id,
        ItemStudent.id == student_id,
    )
    student = db.scalar(stmt)
    if student is None:
        return item, None

    student.parent_message = parent_message.strip()
    db.add(student)
    db.commit()
    db.refresh(student)
    return item, student


def generate_student_commentary(
    item: Item,
    student: ItemStudent,
    metrics: list[dict],
) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DeepSeek API key 未配置。")

    color_name = COLOR_NAME_MAP.get((student.color_hex or "").lower(), "课堂颜色")
    metric_lines = "\n".join(
        f"- {metric['label']}：{metric['score']}/20；说明：{metric['description']}"
        for metric in metrics
    )
    prompt = f"""请你扮演一位细致、温和、专业的小学教师助手，基于以下课堂数据生成一段学生点评。

要求：
1. 用中文输出。
2. 语气自然、具体，不要空话套话。
3. 先肯定学生表现亮点，再给出 1 到 2 条可执行建议。
4. 点评控制在 120 到 180 字。
5. 不要使用 markdown 标题，不要分点编号，直接输出一段完整点评。

课堂信息：
- 课堂名：{item.item_name}
- 班级：{item.class_name}
- 教师：{item.teacher}

学生信息：
- 姓名：{student.student_name or f"学生{student.student_number}"}
- 性别：{student.sex or "未填写"}
- 座位序号：{student.student_number}
- 总颜色：{color_name}
- 总分：{student.score}

五维表现：
{metric_lines}
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "你是一位擅长课堂观察与学生成长反馈的教学助手。",
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "temperature": 0.7,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        "https://api.deepseek.com/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=45) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"DeepSeek 接口返回错误：{detail or exc.reason}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"无法连接 DeepSeek：{exc.reason}") from exc

    try:
        data = json.loads(raw)
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("DeepSeek 返回结果解析失败。") from exc
