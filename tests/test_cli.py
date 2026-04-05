from __future__ import annotations

from pathlib import Path

import fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from pdf_word_replacer.core import ReplacementRule, replace_text_in_pdf


def _make_sample_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setFont("Helvetica", 16)
    pdf.drawString(72, 800, "Hello Alice")
    pdf.drawString(72, 770, "Project Meadow")
    pdf.save()


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
        ],
    )

    assert output_pdf.exists()
    assert results["Alice"] >= 1
    assert results["Meadow"] >= 1

    doc = fitz.open(output_pdf)
    try:
        text = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()

    assert "Burak" in text
    assert "Garden" in text
    assert "Alice" not in text
