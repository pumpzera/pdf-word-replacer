from __future__ import annotations

from pathlib import Path

import fitz
import pytest
import reportlab
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from pdf_word_replacer.core import ReplacementRule, replace_text_in_pdf


def _make_sample_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setFont("Helvetica", 16)
    pdf.drawString(72, 800, "Hello Alice")
    pdf.drawString(72, 770, "Project Meadow")
    pdf.setFont("Times-Roman", 18)
    pdf.drawString(72, 740, "Owner Marco")
    pdf.save()


def _make_type0_font_pdf(path: Path) -> None:
    font_path = Path(reportlab.__file__).resolve().parent / "fonts" / "Vera.ttf"
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_font(fontname="FBUF0", fontbuffer=font_path.read_bytes())
        page.insert_text((72, 72), "NATURAL DIAMOND", fontsize=16, fontname="FBUF0")
        doc.save(path)
    finally:
        doc.close()


def _find_substring_origin(path: Path, needle: str) -> tuple[float, float]:
    doc = fitz.open(path)
    try:
        for page in doc:
            raw = page.get_text("rawdict")
            for block in raw.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        chars = span.get("chars", [])
                        text = "".join(char.get("c", "") for char in chars)
                        start = text.find(needle)
                        if start < 0:
                            continue
                        origin = chars[start].get("origin")
                        if origin:
                            return (float(origin[0]), float(origin[1]))
    finally:
        doc.close()

    raise AssertionError(f"Substring not found: {needle}")


def _find_span_style(path: Path, needle: str) -> tuple[str, float]:
    doc = fitz.open(path)
    try:
        for page in doc:
            raw = page.get_text("rawdict")
            for block in raw.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = "".join(char.get("c", "") for char in span.get("chars", []))
                        if needle in text:
                            return (str(span.get("font")), float(span.get("size", 0)))
    finally:
        doc.close()

    raise AssertionError(f"Span not found: {needle}")


def _find_search_rect(path: Path, needle: str) -> fitz.Rect:
    doc = fitz.open(path)
    try:
        for page in doc:
            rects = page.search_for(needle)
            if rects:
                return fitz.Rect(rects[0])
    finally:
        doc.close()

    raise AssertionError(f"Search rect not found: {needle}")


def test_replace_text_in_pdf(tmp_path: Path) -> None:
    input_pdf = tmp_path / "input.pdf"
    output_pdf = tmp_path / "output.pdf"
    _make_sample_pdf(input_pdf)

    results = replace_text_in_pdf(
        input_pdf,
        output_pdf,
        [
            ReplacementRule("Alice", "Burak"),
            ReplacementRule("Meadow", "Garden"),
            ReplacementRule("Marco", "Luca"),
        ],
    )

    assert output_pdf.exists()
    assert results["Alice"] >= 1
    assert results["Meadow"] >= 1
    assert results["Marco"] >= 1

    doc = fitz.open(output_pdf)
    try:
        text = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()

    assert "Burak" in text
    assert "Garden" in text
    assert "Luca" in text
    assert "Alice" not in text

    alice_origin = _find_substring_origin(input_pdf, "Alice")
    meadow_origin = _find_substring_origin(input_pdf, "Meadow")
    marco_origin = _find_substring_origin(input_pdf, "Marco")
    burak_origin = _find_substring_origin(output_pdf, "Burak")
    garden_origin = _find_substring_origin(output_pdf, "Garden")
    luca_origin = _find_substring_origin(output_pdf, "Luca")
    burak_font, burak_size = _find_span_style(output_pdf, "Burak")
    garden_font, garden_size = _find_span_style(output_pdf, "Garden")
    luca_font, luca_size = _find_span_style(output_pdf, "Luca")

    assert burak_origin[0] == pytest.approx(alice_origin[0], abs=0.01)
    assert burak_origin[1] == pytest.approx(alice_origin[1], abs=0.01)
    assert garden_origin[0] == pytest.approx(meadow_origin[0], abs=0.01)
    assert garden_origin[1] == pytest.approx(meadow_origin[1], abs=0.01)
    assert luca_origin[0] == pytest.approx(marco_origin[0], abs=0.01)
    assert luca_origin[1] == pytest.approx(marco_origin[1], abs=0.01)
    assert burak_font == "Helvetica"
    assert garden_font == "Helvetica"
    assert luca_font == "Times-Roman"
    assert burak_size == pytest.approx(16.0, abs=0.01)
    assert garden_size == pytest.approx(16.0, abs=0.01)
    assert luca_size == pytest.approx(18.0, abs=0.01)


def test_replace_text_in_pdf_falls_back_for_type0_fonts(tmp_path: Path) -> None:
    input_pdf = tmp_path / "type0-input.pdf"
    output_pdf = tmp_path / "type0-output.pdf"
    _make_type0_font_pdf(input_pdf)

    results = replace_text_in_pdf(
        input_pdf,
        output_pdf,
        [ReplacementRule("NATURAL", "FAKE")],
    )

    assert output_pdf.exists()
    assert results["NATURAL"] >= 1

    doc = fitz.open(output_pdf)
    try:
        text = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()

    assert "FAKE" in text
    assert "NATURAL" not in text

    natural_origin = _find_substring_origin(input_pdf, "NATURAL")
    fake_origin = _find_substring_origin(output_pdf, "FAKE")
    fake_font, fake_size = _find_span_style(output_pdf, "FAKE")
    fake_rect = _find_search_rect(output_pdf, "FAKE")
    diamond_rect = _find_search_rect(output_pdf, "DIAMOND")

    assert fake_origin[1] == pytest.approx(natural_origin[1], abs=0.01)
    assert fake_font == "Helvetica"
    assert fake_size == pytest.approx(16.0, abs=0.01)
    assert fake_origin[0] > natural_origin[0]
    assert diamond_rect.x0 - fake_rect.x1 < 10
