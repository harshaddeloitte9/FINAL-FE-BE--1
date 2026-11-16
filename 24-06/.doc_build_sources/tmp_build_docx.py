"""
Markdown -> Word (.docx) converter for the Aegis Credit Director/Manager
reference document. Supports a practical subset of Markdown:
  # / ## / ### / #### headings
  - bullet lists (single level)
  1. numbered lists (single level)
  > blockquote / callout (rendered as shaded indented paragraph)
  --- on its own line => page break
  | pipe | tables | with a |---|---| header-separator row
  ```fenced code blocks```
  inline **bold**, *italic*, `code`
Reads one or more input .md files (concatenated in the order given) and
writes a single .docx.
"""
import sys
import re
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def set_cell_background(cell, color_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color_hex)
    tcPr.append(shd)


def add_inline_runs(paragraph, text):
    """Parse **bold**, *italic*, `code` inline and add runs to paragraph."""
    pattern = re.compile(r"(\*\*.+?\*\*|`.+?`|\*[^*]+?\*)")
    parts = pattern.split(text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = paragraph.add_run(part[2:-2])
            r.bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = paragraph.add_run(part[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(0xB0, 0x3A, 0x2E)
        elif part.startswith("*") and part.endswith("*") and len(part) > 1:
            r = paragraph.add_run(part[1:-1])
            r.italic = True
        else:
            paragraph.add_run(part)


def is_table_sep(line):
    return bool(re.match(r"^\s*\|?[\s:\-\|]+\|?\s*$", line)) and "-" in line


def parse_table_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def build_docx(md_texts, out_path):
    doc = Document()

    # Base styles
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)

    for i in range(1, 5):
        h = doc.styles[f"Heading {i}"]
        h.font.name = "Calibri"
        h.font.color.rgb = RGBColor(0x1F, 0x2D, 0x50)

    doc.styles["Heading 1"].font.size = Pt(20)
    doc.styles["Heading 2"].font.size = Pt(15)
    doc.styles["Heading 3"].font.size = Pt(12.5)
    doc.styles["Heading 4"].font.size = Pt(11)

    section = doc.sections[0]
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)

    full_text = "\n\n".join(md_texts)
    lines = full_text.split("\n")

    i = 0
    n = len(lines)
    in_code = False
    code_buf = []

    while i < n:
        raw = lines[i]
        line = raw.rstrip()

        # Fenced code block
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                in_code = False
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.5)
                run = p.add_run("\n".join(code_buf))
                run.font.name = "Consolas"
                run.font.size = Pt(8.5)
                # light gray shading via a 1-cell table would be nicer, but
                # keep it simple/robust: shaded paragraph background
                pPr = p._p.get_or_add_pPr()
                shd = OxmlElement('w:shd')
                shd.set(qn('w:val'), 'clear')
                shd.set(qn('w:fill'), 'F2F2F2')
                pPr.append(shd)
            i += 1
            continue
        if in_code:
            code_buf.append(raw)
            i += 1
            continue

        if not line.strip():
            i += 1
            continue

        # Page break marker
        if line.strip() == "---":
            doc.add_page_break()
            i += 1
            continue

        # Table
        if line.strip().startswith("|") and i + 1 < n and is_table_sep(lines[i + 1]):
            header = parse_table_row(line)
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(parse_table_row(lines[i]))
                i += 1
            ncols = len(header)
            table = doc.add_table(rows=1, cols=ncols)
            table.style = "Light Grid Accent 1"
            table.alignment = WD_TABLE_ALIGNMENT.LEFT
            hdr_cells = table.rows[0].cells
            for c, htext in enumerate(header):
                if c < ncols:
                    hdr_cells[c].text = ""
                    p = hdr_cells[c].paragraphs[0]
                    r = p.add_run(htext)
                    r.bold = True
                    r.font.size = Pt(9.5)
                    set_cell_background(hdr_cells[c], "1F2D50")
                    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            for row_vals in rows:
                row_cells = table.add_row().cells
                for c in range(ncols):
                    val = row_vals[c] if c < len(row_vals) else ""
                    row_cells[c].text = ""
                    p = row_cells[c].paragraphs[0]
                    add_inline_runs(p, val)
                    for run in p.runs:
                        run.font.size = Pt(9.5)
            doc.add_paragraph()
            continue

        # Headings
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            h = doc.add_heading(level=level)
            add_inline_runs(h, text)
            i += 1
            continue

        # Blockquote / callout
        if line.strip().startswith("> "):
            text = line.strip()[2:]
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.7)
            pPr = p._p.get_or_add_pPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:fill'), 'EDF1FA')
            pPr.append(shd)
            r = p.add_run("")
            add_inline_runs(p, text)
            for run in p.runs:
                run.italic = True
            i += 1
            continue

        # Bullet list
        if re.match(r"^\s*[-*]\s+", line):
            text = re.sub(r"^\s*[-*]\s+", "", line)
            p = doc.add_paragraph(style="List Bullet")
            add_inline_runs(p, text)
            i += 1
            continue

        # Numbered list
        if re.match(r"^\s*\d+[.)]\s+", line):
            text = re.sub(r"^\s*\d+[.)]\s+", "", line)
            p = doc.add_paragraph(style="List Number")
            add_inline_runs(p, text)
            i += 1
            continue

        # Plain paragraph
        p = doc.add_paragraph()
        add_inline_runs(p, line.strip())
        i += 1

    doc.save(out_path)
    print(f"Wrote {out_path} ({len(full_text)} chars source)")


if __name__ == "__main__":
    out = sys.argv[1]
    inputs = sys.argv[2:]
    texts = []
    for path in inputs:
        with open(path, "r", encoding="utf-8") as f:
            texts.append(f.read())
    build_docx(texts, out)
