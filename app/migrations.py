from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_existing_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "heatmap_seat" in table_names:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS `heatmap_seat`"))
        table_names.discard("heatmap_seat")

    if "heatmap_analysis" in table_names:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS `heatmap_analysis`"))
        table_names.discard("heatmap_analysis")

    if "Item" in table_names:
        item_columns = {column["name"] for column in inspector.get_columns("Item")}
        if "created_at" not in item_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE `Item` "
                        "ADD COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
                        "COMMENT '创建时间'"
                    )
                )

    if "Student_score" in table_names:
        student_columns = {column["name"] for column in inspector.get_columns("Student_score")}
        statements = []
        if "student_number" not in student_columns:
            statements.append(
                "ADD COLUMN `student_number` INT NOT NULL DEFAULT 0 COMMENT '座位序号'"
            )
        if "row_number" not in student_columns:
            statements.append("ADD COLUMN `row_number` INT NOT NULL DEFAULT 0 COMMENT '排'")
        if "column_number" not in student_columns:
            statements.append("ADD COLUMN `column_number` INT NOT NULL DEFAULT 0 COMMENT '列'")
        if "color_hex" not in student_columns:
            statements.append("ADD COLUMN `color_hex` VARCHAR(7) NOT NULL DEFAULT '#2f6bff' COMMENT '颜色'")
        if "parent_message" not in student_columns:
            statements.append(
                "ADD COLUMN `parent_message` VARCHAR(1000) NOT NULL DEFAULT '' COMMENT '家长赠语'"
            )
        if "created_at" not in student_columns:
            statements.append(
                "ADD COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"
            )
        if statements:
            with engine.begin() as connection:
                connection.execute(text(f"ALTER TABLE `Student_score` {', '.join(statements)}"))

        if "hidden_score" in student_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE `Student_score` DROP COLUMN `hidden_score`"))

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE `Student_score` s "
                    "JOIN ("
                    "  SELECT id, "
                    "  ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY `column_number` ASC, `row_number` DESC, id ASC) AS rn "
                    "  FROM `Student_score`"
                    ") ranked ON s.id = ranked.id "
                    "SET s.student_number = ranked.rn"
                )
            )
            connection.execute(
                text(
                    "UPDATE `Student_score` s "
                    "JOIN ("
                    "  SELECT id, "
                    "  NTILE(5) OVER (PARTITION BY item_id ORDER BY score ASC, student_number ASC, id ASC) AS tile "
                    "  FROM `Student_score`"
                    ") ranked ON s.id = ranked.id "
                    "SET s.color_hex = CASE ranked.tile "
                    "  WHEN 1 THEN '#2f6bff' "
                    "  WHEN 2 THEN '#35b56a' "
                    "  WHEN 3 THEN '#f3c64d' "
                    "  WHEN 4 THEN '#f08a32' "
                    "  ELSE '#d94b3d' "
                    "END"
                )
            )
