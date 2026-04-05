# PDF Word Replacer

Python CLI tool that replaces visible text in text-based PDF files.

## What it does

- Replaces one or more words or short phrases in a PDF
- Saves the edited PDF as a new file
- Works best on selectable-text PDFs
- Keeps the original font, font size, color, and text baseline when the match comes from the PDF text layer

## Super Simple Explanation

If you have a PDF and want to change a word inside it, this tool does that.

Example:

- Your PDF says `John`
- You want it to say `Jane`
- This tool opens the PDF, finds `John`, and writes `Jane` in the same place

You choose:

- which PDF to edit
- where the new edited PDF will be saved
- which word should change
- what the new word should be

The original PDF is not changed unless you overwrite it on purpose.

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

## Step By Step

### 1. Open PowerShell

Open Windows PowerShell.

### 2. Go to this project folder

```powershell
cd "C:\path\to\pdf-word-replacer"
```

### 3. Install the tool

You only need to do this once:

```powershell
python -m pip install -e .
```

### 4. Run the command

Basic format:

```powershell
python -m pdf_word_replacer.cli "INPUT_PDF" "OUTPUT_PDF" --replace old=new
```

What each part means:

- `INPUT_PDF` = the PDF you want to edit
- `OUTPUT_PDF` = the new PDF that will be created
- `--replace old=new` = change the word `old` into `new`

### 5. Real example

```powershell
python -m pdf_word_replacer.cli "C:\Users\Bugra\Documents\contract.pdf" "C:\Users\Bugra\Documents\contract-edited.pdf" --replace John=Jane
```

This means:

- open `contract.pdf`
- find `John`
- replace it with `Jane`
- save the result as `contract-edited.pdf`

## Quick Start Examples

Replace a single word:

```bash
python -m pdf_word_replacer.cli "input.pdf" "output.pdf" --replace old=new
```

Replace multiple words:

```bash
python -m pdf_word_replacer.cli "input.pdf" "output.pdf" --replace old=new --replace hello=world
```

Replace a phrase for cleaner layout:

```bash
python -m pdf_word_replacer.cli "input.pdf" "output.pdf" --replace "Meadow City=Garden City"
```

Use case-insensitive matching:

```bash
python -m pdf_word_replacer.cli "input.pdf" "output.pdf" --replace old=new --ignore-case
```

## If You Want To Edit Your Own PDF

Use this template and just change the file paths and words:

```powershell
python -m pdf_word_replacer.cli "C:\PATH\TO\YOUR\INPUT.pdf" "C:\PATH\TO\YOUR\OUTPUT.pdf" --replace oldword=newword
```

Example:

```powershell
python -m pdf_word_replacer.cli "C:\Users\Bugra\Desktop\file.pdf" "C:\Users\Bugra\Desktop\file-edited.pdf" --replace Apple=Orange
```

## What Happens After You Run It

- The tool reads the input PDF
- It searches for the word or phrase you gave
- It replaces the text in the PDF
- It saves a new PDF at the output path

If the command succeeds, you will see a message like this:

```text
Saved: C:\path\to\output.pdf
Total replacements: 1
- John: 1
```

## Common Mistakes

- If Python says the file does not exist, your PDF path is wrong
- If nothing changes, the PDF may be scanned or image-based
- If the new word is much longer, it may visually collide with nearby text
- If your path has spaces, keep it inside quotes like `"C:\My Folder\file.pdf"`

## Command Reference

```bash
python -m pdf_word_replacer.cli INPUT_PDF OUTPUT_PDF --replace SOURCE=TARGET [--replace SOURCE=TARGET ...] [--ignore-case]
```

## Notes

- The original file is not modified unless you choose the same input and output path
- The edited PDF is saved exactly where you tell the tool to save it
- Exact visual results still depend on how the original PDF stores its text
