"""Tiny python-docx helpers used by both lab-report builders."""
import os
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


def new_doc():
    d = Document()
    sec = d.sections[0]
    sec.left_margin = sec.right_margin = Inches(1)
    sec.top_margin = sec.bottom_margin = Inches(0.9)
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    st.paragraph_format.space_after = Pt(6)
    for name, size, color in (("Heading 1", 18, "1F3864"), ("Heading 2", 14, "2E5597"), ("Heading 3", 12, "2E5597")):
        h = d.styles[name]; h.font.name = "Calibri"; h.font.size = Pt(size); h.font.bold = True
        h.font.color.rgb = RGBColor.from_string(color)
        h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        h.paragraph_format.space_before = Pt(14 if name != "Heading 3" else 10); h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
    # page number footer
    p = sec.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for t, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        r = p.add_run()
        if t:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), t); r._r.append(e)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt; r._r.append(e)
    return d


def title_page(d, course, unit, sub):
    for _ in range(5):
        d.add_paragraph()
    p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(course); r.bold = True; r.font.size = Pt(28); r.font.color.rgb = RGBColor.from_string("1F3864")
    p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(unit); r.font.size = Pt(18)
    p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(sub); r.font.size = Pt(13); r.italic = True
    for _ in range(3):
        d.add_paragraph()
    t = d.add_table(rows=4, cols=2); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate((("Student name", "[your name]"), ("Roll no. / ID", "[your ID]"),
                                ("Course / section", "[course, section]"), ("Date", "17 November 2026"))):
        t.cell(i, 0).text = k; t.cell(i, 1).text = v
        t.cell(i, 0).paragraphs[0].runs[0].bold = True
        t.cell(i, 0).width = Inches(1.8); t.cell(i, 1).width = Inches(3.2)
    d.add_page_break()


def h(d, text, lvl=1):
    return d.add_heading(text, lvl)


def para(d, text, bold_prefix=None, italic=False, size=None):
    p = d.add_paragraph()
    if bold_prefix:
        r = p.add_run(bold_prefix); r.bold = True
    r = p.add_run(text); r.italic = italic
    if size:
        for rr in p.runs:
            rr.font.size = Pt(size)
    return p


def bullets(d, items):
    for it in items:
        p = d.add_paragraph(style="List Bullet")
        if isinstance(it, tuple):
            r = p.add_run(it[0]); r.bold = True; p.add_run(it[1])
        else:
            p.add_run(it)
        p.paragraph_format.space_after = Pt(2)


def numbered(d, items):
    for it in items:
        p = d.add_paragraph(style="List Number"); p.add_run(it); p.paragraph_format.space_after = Pt(2)


def _shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), color)
    tcPr.append(sh)


def table(d, header, rows, widths=None, size=9, caption=None, bold_rows=()):
    if caption:
        cp = d.add_paragraph(); r = cp.add_run(caption); r.bold = True; r.font.size = Pt(10)
        cp.paragraph_format.keep_with_next = True; cp.paragraph_format.space_after = Pt(2)
    t = d.add_table(rows=1, cols=len(header)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, x in enumerate(header):
        c = t.rows[0].cells[i]; c.text = ""
        r = c.paragraphs[0].add_run(str(x)); r.bold = True; r.font.size = Pt(size)
        r.font.color.rgb = RGBColor(255, 255, 255); _shade(c, "2E5597")
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, x in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(x)); r.font.size = Pt(size)
            if ri in bold_rows:
                r.bold = True
            if ri % 2 == 1:
                _shade(cells[i], "EAF0FA")
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(1)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    d.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figure(d, path, caption, width=6.3):
    p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(path, width=Inches(width))
    c = d.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = c.add_run(caption); r.italic = True; r.font.size = Pt(9.5)


def code_block(d, text, size=7):
    for line in text.split("\n"):
        p = d.add_paragraph(); p.paragraph_format.space_after = Pt(0); p.paragraph_format.space_before = Pt(0)
        r = p.add_run(line if line else " "); r.font.name = "Consolas"; r.font.size = Pt(size)
        r._r.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")


def words(text):
    return len(text.split())
