from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

import fitz


@dataclass(frozen=True)
class ReplacementRule:
    source: str
    target: str


@dataclass(frozen=True)
class _LineChar:
    text: str
    rect: fitz.Rect
    origin: fitz.Point
    fontname: str
    fontsize: float
    color: tuple[float, float, float]


@dataclass(frozen=True)
class _PlannedReplacement:
    source: str
    target: str
    rect: fitz.Rect
    origin: fitz.Point
    fontname: str
    fontsize: float
    color: tuple[float, float, float]


def _int_to_rgb(value: int) -> tuple[float, float, float]:
    red = ((value >> 16) & 255) / 255
    green = ((value >> 8) & 255) / 255
    blue = (value & 255) / 255
    return (red, green, blue)


def _strip_subset_prefix(font_name: str) -> str:
    if "+" not in font_name:
        return font_name

    prefix, suffix = font_name.split("+", 1)
    if len(prefix) == 6 and prefix.isalpha() and prefix.isupper():
        return suffix
    return font_name


def _normalize_font_key(font_name: str) -> str:
    font_name = _strip_subset_prefix(str(font_name or ""))
    return "".join(char for char in font_name.casefold() if char.isalnum())


def _get_page_font_entries(page: fitz.Page) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for font in page.get_fonts():
        if len(font) < 5:
            continue
        _, _, _, basefont, resource_name, *_ = font
        preferred = str(resource_name or basefont or "")
        if not preferred:
            continue

        for candidate in (resource_name, basefont, _strip_subset_prefix(str(basefont or ""))):
            key = _normalize_font_key(str(candidate or ""))
            item = (key, preferred)
            if not key or item in seen:
                continue
            entries.append(item)
            seen.add(item)

    return entries


def _resolve_fontname(font_entries: list[tuple[str, str]], span_font: str) -> str:
    span_key = _normalize_font_key(span_font)

    if span_key:
        for entry_key, fontname in font_entries:
            if entry_key == span_key:
                return fontname

        for entry_key, fontname in font_entries:
            if span_key in entry_key or entry_key in span_key:
                return fontname

    return str(span_font or "helv")


def _iter_line_chars(page: fitz.Page) -> Iterable[list[_LineChar]]:
    font_entries = _get_page_font_entries(page)
    text = page.get_text("rawdict")

    for block in text.get("blocks", []):
        for line in block.get("lines", []):
            line_chars: list[_LineChar] = []
            for span in line.get("spans", []):
                fontname = _resolve_fontname(font_entries, str(span.get("font", "")))
                fontsize = float(span.get("size", 11.0))
                color = _int_to_rgb(int(span.get("color", 0)))

                for char in span.get("chars", []):
                    glyph = str(char.get("c", ""))
                    bbox = char.get("bbox")
                    origin = char.get("origin")
                    if not glyph or not bbox or not origin:
                        continue

                    line_chars.append(
                        _LineChar(
                            text=glyph,
                            rect=fitz.Rect(bbox),
                            origin=fitz.Point(origin),
                            fontname=fontname,
                            fontsize=fontsize,
                            color=color,
                        )
                    )

            if line_chars:
                yield line_chars


def _build_line_text(line_chars: list[_LineChar]) -> tuple[str, list[tuple[int, int]]]:
    text_parts: list[str] = []
    char_ranges: list[tuple[int, int]] = []
    cursor = 0

    for line_char in line_chars:
        text_parts.append(line_char.text)
        next_cursor = cursor + len(line_char.text)
        char_ranges.append((cursor, next_cursor))
        cursor = next_cursor

    return "".join(text_parts), char_ranges


def _find_text_matches(source_text: str, needle: str, ignore_case: bool) -> list[tuple[int, int]]:
    if not needle:
        return []

    flags = re.IGNORECASE if ignore_case else 0
    return [(match.start(), match.end()) for match in re.finditer(re.escape(needle), source_text, flags)]


def _text_range_to_char_range(
    char_ranges: list[tuple[int, int]],
    start: int,
    end: int,
) -> tuple[int, int] | None:
    first_index: int | None = None
    last_index: int | None = None

    for index, (char_start, char_end) in enumerate(char_ranges):
        if char_end <= start:
            continue
        if char_start >= end:
            break
        if first_index is None:
            first_index = index
        last_index = index + 1

    if first_index is None or last_index is None:
        return None

    return first_index, last_index


def _merge_rects(chars: list[_LineChar]) -> fitz.Rect:
    rect = fitz.Rect(chars[0].rect)
    for line_char in chars[1:]:
        rect.include_rect(line_char.rect)
    return rect


def _plan_page_replacements(
    page: fitz.Page,
    rules: Iterable[ReplacementRule],
    ignore_case: bool,
) -> list[_PlannedReplacement]:
    planned: list[_PlannedReplacement] = []

    for line_chars in _iter_line_chars(page):
        line_text, char_ranges = _build_line_text(line_chars)
        occupied = [False] * len(line_chars)

        for rule in rules:
            for start, end in _find_text_matches(line_text, rule.source, ignore_case):
                char_range = _text_range_to_char_range(char_ranges, start, end)
                if char_range is None:
                    continue

                char_start, char_end = char_range
                if any(occupied[char_start:char_end]):
                    continue

                matched_chars = line_chars[char_start:char_end]
                first_char = matched_chars[0]
                planned.append(
                    _PlannedReplacement(
                        source=rule.source,
                        target=rule.target,
                        rect=_merge_rects(matched_chars),
                        origin=fitz.Point(first_char.origin),
                        fontname=first_char.fontname,
                        fontsize=first_char.fontsize,
                        color=first_char.color,
                    )
                )

                for index in range(char_start, char_end):
                    occupied[index] = True

    return planned


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
            replacements = _plan_page_replacements(page, rules, ignore_case)
            if not replacements:
                continue

            for replacement in replacements:
                page.add_redact_annot(replacement.rect, fill=(1, 1, 1))
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            for replacement in replacements:
                if replacement.target:
                    try:
                        page.insert_text(
                            replacement.origin,
                            replacement.target,
                            fontsize=replacement.fontsize,
                            fontname=replacement.fontname,
                            color=replacement.color,
                            overlay=True,
                        )
                    except Exception:
                        page.insert_text(
                            replacement.origin,
                            replacement.target,
                            fontsize=replacement.fontsize,
                            fontname="helv",
                            color=replacement.color,
                            overlay=True,
                        )
                applied[replacement.source] += 1

        doc.save(output_path, garbage=4, deflate=True)
    finally:
        doc.close()

    return applied
