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
    text_align: str


@dataclass(frozen=True)
class _PageFontEntry:
    resource_name: str
    basefont: str
    font_type: str
    encoding: str


_SANS_HINTS = (
    "arial",
    "helvetica",
    "calibri",
    "microsoftsansserif",
    "segoe",
    "verdana",
    "tahoma",
    "trebuchet",
    "geneva",
    "dejavusans",
    "notosans",
    "bitstreamverasans",
    "frutiger",
    "univers",
    "gothic",
    "kakugo",
    "sans",
)

_SERIF_HINTS = (
    "times",
    "georgia",
    "garamond",
    "cambria",
    "baskerville",
    "palatino",
    "bookman",
    "dejavuserif",
    "notoserif",
    "libertine",
    "song",
    "mincho",
    "heiseimin",
    "serif",
)

_MONO_HINTS = (
    "courier",
    "consolas",
    "monaco",
    "lucidaconsole",
    "menlo",
    "dejavusansmono",
    "firacode",
    "sourcecodepro",
    "jetbrainsmono",
    "ibmplexmono",
    "monospace",
    "mono",
)

_BOLD_HINTS = ("bold", "black", "heavy", "demi", "semibold")
_ITALIC_HINTS = ("italic", "oblique", "slanted")
_BUILTIN_FONT_KEYS = {
    "".join(char for char in str(name).casefold() if char.isalnum())
    for name in (*fitz.Base14_fontdict.keys(), *fitz.Base14_fontdict.values())
}


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


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def _is_direct_insert_font(entry: _PageFontEntry) -> bool:
    font_type = entry.font_type.casefold()
    encoding = entry.encoding.casefold()

    if font_type == "type0":
        return False
    if encoding.startswith("identity"):
        return False
    return True


def _pick_builtin_fallback(*font_names: str) -> str:
    keys = " ".join(_normalize_font_key(name) for name in font_names if name)
    is_bold = _contains_any(keys, _BOLD_HINTS)
    is_italic = _contains_any(keys, _ITALIC_HINTS)

    if _contains_any(keys, _MONO_HINTS):
        if is_bold and is_italic:
            return "cobi"
        if is_bold:
            return "cobo"
        if is_italic:
            return "coit"
        return "cour"

    if _contains_any(keys, _SANS_HINTS):
        if is_bold and is_italic:
            return "hebi"
        if is_bold:
            return "hebo"
        if is_italic:
            return "heit"
        return "helv"

    if _contains_any(keys, _SERIF_HINTS):
        if is_bold and is_italic:
            return "tibi"
        if is_bold:
            return "tibo"
        if is_italic:
            return "tiit"
        return "tiro"

    if is_bold and is_italic:
        return "hebi"
    if is_bold:
        return "hebo"
    if is_italic:
        return "heit"
    return "helv"


def _measure_text_width(text: str, fontname: str, fontsize: float) -> float | None:
    font_key = _normalize_font_key(fontname)
    if font_key not in _BUILTIN_FONT_KEYS:
        return None

    try:
        return float(fitz.get_text_length(text, fontname=fontname, fontsize=fontsize))
    except Exception:
        return None


def _pick_text_alignment(line_text: str, start: int, end: int) -> str:
    leading_text = line_text[:start].strip()
    trailing_text = line_text[end:].strip()

    if trailing_text and not leading_text:
        return "right"
    if leading_text and trailing_text:
        return "center"
    return "left"


def _adjust_text_origin(replacement: _PlannedReplacement) -> fitz.Point:
    text_width = _measure_text_width(
        replacement.target,
        replacement.fontname,
        replacement.fontsize,
    )
    if text_width is None or text_width >= replacement.rect.width:
        return replacement.origin

    if replacement.text_align == "right":
        x_pos = replacement.rect.x1 - text_width
    elif replacement.text_align == "center":
        x_pos = replacement.rect.x0 + (replacement.rect.width - text_width) / 2
    else:
        x_pos = replacement.origin.x

    x_pos = max(replacement.rect.x0, x_pos)
    return fitz.Point(x_pos, replacement.origin.y)


def _get_page_font_entries(page: fitz.Page) -> dict[str, _PageFontEntry]:
    entries: dict[str, _PageFontEntry] = {}

    for font in page.get_fonts():
        if len(font) < 5:
            continue
        _, _, font_type, basefont, resource_name, *rest = font
        encoding = str(rest[0]) if rest else ""
        entry = _PageFontEntry(
            resource_name=str(resource_name or ""),
            basefont=str(basefont or ""),
            font_type=str(font_type or ""),
            encoding=encoding,
        )

        if not entry.resource_name and not entry.basefont:
            continue

        for candidate in (
            entry.resource_name,
            entry.basefont,
            _strip_subset_prefix(entry.basefont),
        ):
            key = _normalize_font_key(str(candidate or ""))
            if not key or key in entries:
                continue
            entries[key] = entry

    return entries


def _find_font_entry(font_entries: dict[str, _PageFontEntry], span_font: str) -> _PageFontEntry | None:
    span_key = _normalize_font_key(span_font)

    if span_key:
        if span_key in font_entries:
            return font_entries[span_key]

        for entry_key, entry in font_entries.items():
            if span_key in entry_key or entry_key in span_key:
                return entry

    return None


def _resolve_fontname(font_entries: dict[str, _PageFontEntry], span_font: str) -> str:
    entry = _find_font_entry(font_entries, span_font)
    if entry is None:
        return _pick_builtin_fallback(span_font)

    if _is_direct_insert_font(entry):
        return entry.resource_name or _pick_builtin_fallback(entry.basefont, span_font)

    return _pick_builtin_fallback(entry.basefont, span_font, entry.resource_name)


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
                        text_align=_pick_text_alignment(line_text, start, end),
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
                    draw_origin = _adjust_text_origin(replacement)
                    try:
                        page.insert_text(
                            draw_origin,
                            replacement.target,
                            fontsize=replacement.fontsize,
                            fontname=replacement.fontname,
                            color=replacement.color,
                            overlay=True,
                        )
                    except Exception:
                        page.insert_text(
                            draw_origin,
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
