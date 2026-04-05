# PDF Word Replacer

Python CLI tool that replaces visible text in text-based PDF files.

## What it does

- Replaces one or more words or short phrases in a PDF
- Saves the edited PDF as a new file
- Works best on selectable-text PDFs
- Keeps the original font, font size, color, and text baseline when the match comes from the PDF text layer

## Limitations

- Scanned/image-only PDFs are not supported unless OCR text already exists
- Complex layouts and text split across multiple drawing objects may still need manual review
- This tool replaces visible text areas; it is not meant for legal or tamper-proof redaction
- PDF line layout is not reflowed; longer replacements can overlap nearby content
- No automatic font shrinking or stretching is applied, so the output keeps the original text sizing

## Install

```bash
python -m pip install -e .
```

For tests:

```bash
python -m pip install -e .[dev]
```

## Quick Start

Replace a single word:

```bash
pdf-word-replacer input.pdf output.pdf --replace old=new
```

Or run it as a module:

```bash
python -m pdf_word_replacer.cli input.pdf output.pdf --replace old=new
```

Replace multiple words:

```bash
pdf-word-replacer input.pdf output.pdf --replace old=new --replace hello=world
```

Replace a phrase for cleaner layout:

```bash
pdf-word-replacer input.pdf output.pdf --replace "Meadow City=Garden City"
```

Use case-insensitive matching:

```bash
pdf-word-replacer input.pdf output.pdf --replace old=new --ignore-case
```

## CLI

```bash
pdf-word-replacer INPUT_PDF OUTPUT_PDF --replace SOURCE=TARGET [--replace SOURCE=TARGET ...] [--ignore-case]
```

## Example

```bash
pdf-word-replacer contract.pdf contract-edited.pdf --replace John=Jane --replace London=Berlin
```

## Notes

- Original file is never modified
- Output PDF is written to the path you choose
- Exact visual results still depend on how the original PDF stores its text
