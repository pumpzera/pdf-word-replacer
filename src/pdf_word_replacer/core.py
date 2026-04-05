from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz


@dataclass(frozen=True)
class ReplacementRule:
    source: str
    target: str


def _int_to_rgb(value: int) -> tuple[float, float, float]:
    red = ((value >> 16) & 255) / 255
    green = ((value >> 8) & 255) / 255
    blue = (value & 255) / 255
    return (red, green, blue)


def _rect_intersects(a: fitz.Rect, b: fitz.Rect) -> bool:
    return not (a.x1 < b.x0 or a.x0 > b.x1 or a.y1 < b.y0 or a.y0 > b.y1)


def _find_span_style(page: fitz.Page, rect: fitz.Rect) -> tuple[float, tuple[float, float, float]]:
    text = page.get_text("dict")
    best_size = 11.0
    best_color = (0.0, 0.0, 0.0)

    for block in text.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_bbox = span.get("bbox")
                if not span_bbox:
                    continue
                span_rect = fitz.Rect(span_bbox)
                if not _rect_intersects(rect, span_rect):
                    continue
                size = float(span.get("size", best_size))
                color = _int_to_rgb(int(span.get("color", 0)))
                return size, color

    return best_size, best_color


def _fit_font_size(rect: fitz.Rect, text: str, base_size: float) -> float:
    if not text:
        return base_size

    size = max(base_size, 6.0)
    usable_width = max(rect.width - 2, 4)
    usable_height = max(rect.height - 1, 4)

    while size >= 6.0:
        text_width = fitz.get_text_length(text, fontname="helv", fontsize=size)
        if text_width <= usable_width and size <= usable_height * 0.95:
            return size
        size -= 0.5

    return 6.0


def _collect_phrase_hits(
    page: fitz.Page,
    source: str,
    ignore_case: bool,
) -> list[fitz.Rect]:
    hits: list[fitz.Rect] = []
    if not source.strip():
        return hits

    if not ignore_case:
        return list(page.search_for(source))

    needle = source.casefold()
    for rect in page.search_for(source):
        hits.append(rect)

    words = page.get_text("words")
    for x0, y0, x1, y1, word, *_ in words:
        if str(word).casefold() == needle:
            rect = fitz.Rect(x0, y0, x1, y1)
            if not any(existing.contains(rect) or existing == rect for existing in hits):
                hits.append(rect)

    return hits


def replace_text_in_pdf(
    input_path: str | Path,
    output_path: str | Path,
    rules: Iterable[ReplacementRule],
    ignore_case: bool = False,
) -> dict[str, int]:
    input_path = Path(input_path)
    output_path = Path(output_path)
    rules = list(rules)

    if not input_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")
    if not rules:
        raise ValueError("At least one replacement rule is required.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(input_path)
    applied: dict[str, int] = {rule.source: 0 for rule in rules}

    try:
        for page in doc:
            for rule in rules:
                for rect in _collect_phrase_hits(page, rule.source, ignore_case):
                    font_size, color = _find_span_style(page, rect)
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

                    write_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1)
                    fitted_size = _fit_font_size(write_rect, rule.target, font_size)
                    inserted = page.insert_textbox(
                        write_rect,
                        rule.target,
                        fontsize=fitted_size,
                        fontname="helv",
                        color=color,
                        align=fitz.TEXT_ALIGN_LEFT,
                    )
                    if inserted < 0:
                        page.insert_text(
                            fitz.Point(write_rect.x0, write_rect.y1 - 1),
                            rule.target,
                            fontsize=fitted_size,
                            fontname="helv",
                            color=color,
                        )
                    applied[rule.source] += 1

        doc.save(output_path, garbage=4, deflate=True)
    finally:
        doc.close()

    return applied
