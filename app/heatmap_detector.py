from __future__ import annotations

import colorsys
import math
import statistics
import subprocess
import tempfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import png


class HeatmapDetectionError(Exception):
    pass


@dataclass
class SeatDetection:
    seat_number: int
    row_number: int
    column_number: int
    score: int
    color_hex: str
    bbox_left: int
    bbox_top: int
    bbox_width: int
    bbox_height: int


@dataclass
class HeatmapDetectionResult:
    image_path: str
    image_width: int
    image_height: int
    row_count: int
    column_count: int
    seat_count: int
    score_min: int
    score_max: int
    seats: list[SeatDetection]


def _ensure_png(image_path: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if image_path.suffix.lower() == ".png":
        return image_path, None

    temp_dir = tempfile.TemporaryDirectory(prefix="heatmap_png_")
    output_path = Path(temp_dir.name) / f"{image_path.stem}.png"
    command = ["sips", "-s", "format", "png", str(image_path), "--out", str(output_path)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0 or not output_path.exists():
        temp_dir.cleanup()
        raise HeatmapDetectionError("只能稳定处理 PNG 截图，且自动转换失败。请先转成 PNG 再试。")
    return output_path, temp_dir


def _read_png_rgb(image_path: Path) -> np.ndarray:
    reader = png.Reader(filename=str(image_path))
    width, height, rows, info = reader.read()
    planes = info["planes"]
    row_arrays = [np.asarray(row, dtype=np.uint8) for row in rows]
    image = np.vstack(row_arrays).reshape(height, width, planes)

    if planes == 4:
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        rgb = image[:, :, :3].astype(np.float32)
        background = np.zeros_like(rgb)
        image = (rgb * alpha + background * (1.0 - alpha)).astype(np.uint8)
    elif planes == 3:
        image = image[:, :, :3]
    else:
        raise HeatmapDetectionError("当前只支持 RGB 或 RGBA PNG 图片。")

    return image


def _border_background(image: np.ndarray) -> np.ndarray:
    h, w, _ = image.shape
    pad = max(8, min(h, w) // 40)
    border_pixels = np.concatenate(
        [
            image[:pad, :, :].reshape(-1, 3),
            image[-pad:, :, :].reshape(-1, 3),
            image[:, :pad, :].reshape(-1, 3),
            image[:, -pad:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    return np.median(border_pixels.astype(np.float32), axis=0)


def _seat_mask(image: np.ndarray) -> np.ndarray:
    background = _border_background(image)
    diff = np.mean(np.abs(image.astype(np.float32) - background), axis=2)
    green_path = (
        (image[:, :, 1] > 120)
        & (image[:, :, 1] > image[:, :, 0] + 40)
        & (image[:, :, 1] > image[:, :, 2] + 20)
    )
    return (diff > 16) & (~green_path)


def _connected_components(mask: np.ndarray) -> list[tuple[int, int, int, int, int, np.ndarray]]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[tuple[int, int, int, int, int, np.ndarray]] = []

    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue

            queue: deque[tuple[int, int]] = deque([(y, x)])
            visited[y, x] = True
            pixels: list[tuple[int, int]] = []
            min_y = max_y = y
            min_x = max_x = x

            while queue:
                cy, cx = queue.popleft()
                pixels.append((cy, cx))
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)

                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((ny, nx))

            pixel_array = np.asarray(pixels, dtype=np.int32)
            components.append((min_x, min_y, max_x, max_y, len(pixels), pixel_array))

    return components


def _filter_components(
    components: list[tuple[int, int, int, int, int, np.ndarray]]
) -> list[tuple[int, int, int, int, int, np.ndarray]]:
    filtered = []
    for min_x, min_y, max_x, max_y, area, pixels in components:
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        aspect_ratio = width / max(height, 1)
        fill_ratio = area / max(width * height, 1)

        if width < 40 or height < 20:
            continue
        if width > 260 or height > 130:
            continue
        if aspect_ratio < 1.2 or aspect_ratio > 3.8:
            continue
        if fill_ratio < 0.62:
            continue

        filtered.append((min_x, min_y, max_x, max_y, area, pixels))

    if not filtered:
        raise HeatmapDetectionError("没有识别到座位块。请确认截图里主要内容是热力图本体。")

    return filtered


def _cluster_positions(values: list[float], tolerance: float) -> list[float]:
    clusters: list[list[float]] = []
    for value in sorted(values):
        if not clusters or abs(value - statistics.mean(clusters[-1])) > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [statistics.mean(cluster) for cluster in clusters]


def _rgb_to_hex(color: np.ndarray) -> str:
    red, green, blue = [int(round(v)) for v in color]
    return f"#{red:02x}{green:02x}{blue:02x}"


def _score_from_colors(colors: list[np.ndarray]) -> list[int]:
    if not colors:
        return []

    hsv_values = [colorsys.rgb_to_hsv(*(color / 255.0)) for color in colors]
    saturations = np.array([value[1] for value in hsv_values], dtype=np.float32)
    sorted_indices = np.argsort(saturations)
    anchor_count = max(1, len(colors) // 5)

    low_anchor = np.mean([colors[index] for index in sorted_indices[:anchor_count]], axis=0)
    distances = np.array([np.linalg.norm(color - low_anchor) for color in colors], dtype=np.float32)
    farthest_indices = np.argsort(distances)[-anchor_count:]
    high_anchor = np.mean([colors[index] for index in farthest_indices], axis=0)
    direction = high_anchor - low_anchor
    denom = float(np.dot(direction, direction))

    if denom <= 1e-6:
        return [20 for _ in colors]

    scores = []
    for color in colors:
        projection = float(np.dot(color - low_anchor, direction) / denom)
        normalized = max(0.0, min(1.0, projection))
        score = int(round(20 + normalized * 80))
        scores.append(max(20, min(100, score)))

    return scores


def detect_heatmap(image_path: str) -> HeatmapDetectionResult:
    source_path = Path(image_path).expanduser().resolve()
    if not source_path.exists():
        raise HeatmapDetectionError(f"图片不存在：{source_path}")

    png_path, temp_dir = _ensure_png(source_path)
    try:
        image = _read_png_rgb(png_path)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    height, width, _ = image.shape
    mask = _seat_mask(image)
    components = _filter_components(_connected_components(mask))

    widths = [component[2] - component[0] + 1 for component in components]
    heights = [component[3] - component[1] + 1 for component in components]
    x_centers = [(component[0] + component[2]) / 2 for component in components]
    y_centers = [(component[1] + component[3]) / 2 for component in components]

    x_tolerance = max(18.0, statistics.median(widths) * 0.6)
    y_tolerance = max(12.0, statistics.median(heights) * 0.7)
    column_centers = _cluster_positions(x_centers, x_tolerance)
    row_centers = _cluster_positions(y_centers, y_tolerance)

    seat_rows = []
    mean_colors = []
    for min_x, min_y, max_x, max_y, _area, pixels in components:
        pixel_values = image[pixels[:, 0], pixels[:, 1], :].astype(np.float32)
        mean_color = np.mean(pixel_values, axis=0)
        mean_colors.append(mean_color)

        x_center = (min_x + max_x) / 2
        y_center = (min_y + max_y) / 2
        column_number = min(
            range(len(column_centers)),
            key=lambda index: abs(column_centers[index] - x_center),
        ) + 1
        row_number = min(
            range(len(row_centers)),
            key=lambda index: abs(row_centers[index] - y_center),
        ) + 1

        seat_rows.append(
            {
                "row_number": row_number,
                "column_number": column_number,
                "bbox_left": int(min_x),
                "bbox_top": int(min_y),
                "bbox_width": int(max_x - min_x + 1),
                "bbox_height": int(max_y - min_y + 1),
            }
        )

    scores = _score_from_colors(mean_colors)
    ordered = []
    for row, mean_color, score in zip(seat_rows, mean_colors, scores, strict=True):
        ordered.append(
            {
                **row,
                "score": score,
                "color_hex": _rgb_to_hex(mean_color),
            }
        )

    # Seat numbering follows classroom convention: left-to-right by column,
    # and within each column from bottom to top (left-bottom seat is No.1).
    ordered.sort(key=lambda item: (item["column_number"], -item["row_number"]))
    seats = [
        SeatDetection(
            seat_number=index,
            row_number=item["row_number"],
            column_number=item["column_number"],
            score=item["score"],
            color_hex=item["color_hex"],
            bbox_left=item["bbox_left"],
            bbox_top=item["bbox_top"],
            bbox_width=item["bbox_width"],
            bbox_height=item["bbox_height"],
        )
        for index, item in enumerate(ordered, start=1)
    ]

    if not seats:
        raise HeatmapDetectionError("没有生成有效的座位结果。")

    return HeatmapDetectionResult(
        image_path=str(source_path),
        image_width=int(width),
        image_height=int(height),
        row_count=len(row_centers),
        column_count=len(column_centers),
        seat_count=len(seats),
        score_min=min(seat.score for seat in seats),
        score_max=max(seat.score for seat in seats),
        seats=seats,
    )
