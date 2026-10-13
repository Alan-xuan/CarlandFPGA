#!/usr/bin/env python3
"""Build the Chinese task-book PDF from the candidate markdown.

Usage:
    python build_pdf.py [input.md] [output.pdf]
    python build_pdf.py --input input.md --output output.pdf

Layout: A4, 12pt body with comfortable leading, per-character CJK wrapping with
basic kinsoku rules, gray-bordered tables with a repeating header row, a running
header from page 2 on, and page-number footers.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

DEFAULT_INPUT = os.path.join("docs", "competition", "mine_plan_20261013", "taskbook_candidate.md")
DEFAULT_OUTPUT = os.path.join("output", "pdf", "mine_taskbook_candidate.pdf")
DEFAULT_FONT_PATH = r"C:\Windows\Fonts\simsun.ttc"
DEFAULT_FONT_INDEX = 0
FONT_NAME = "SimSun"

BODY_SIZE = 12.0
BODY_LEADING = 19.5
CELL_SIZE = 11.0
CELL_LEADING = 16.5
CELL_PAD = 6.0
PAGE_MARGIN_X = 20 * mm
PAGE_MARGIN_TOP = 20 * mm
PAGE_MARGIN_BOTTOM = 18 * mm
MIN_COL_WIDTH = 54.0
FIT_TOLERANCE = 0.25
LINK_SIZE = 9.0
LINK_COLOR = "#1a4d8f"
URL_COLOR = "#666666"

LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")
TABLE_SEP_RE = re.compile(r"^:?-{2,}:?$")
ASCII_WORD_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_/\\-.+%@#&:=?[]{}()<>"
)
# Closing punctuation must not start a line, opening punctuation must not end one.
NO_LINE_START = set("，。、；：？！）〕］｝〉》」』】”’…”—·%℃×÷,;:!?)]}")
NO_LINE_END = set("（〔［｛〈《「『【“‘([{")


def escape_xml(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def split_inline(text, base_size=BODY_SIZE):
    """Split markdown text into (char, size, href) specs; link URLs stay visible."""
    specs = []
    pos = 0
    for match in LINK_RE.finditer(text):
        for ch in text[pos:match.start()]:
            specs.append((ch, base_size, None))
        label, url = match.group(1), match.group(2)
        for ch in label:
            specs.append((ch, base_size, url))
        for ch in "（" + url + "）":
            specs.append((ch, LINK_SIZE, url))
        pos = match.end()
    for ch in text[pos:]:
        specs.append((ch, base_size, None))
    return specs


def specs_plain_text(specs):
    return "".join(ch for ch, _size, _href in specs)


def char_width(spec):
    ch, size, _href = spec
    return pdfmetrics.stringWidth(ch, FONT_NAME, size)


def specs_width(specs):
    return sum(char_width(spec) for spec in specs)


def split_long_word(specs, width):
    """Split an over-long ASCII run into chunks that fit; prefer natural breakpoints."""
    chunks = []
    rest = specs
    while rest:
        used = 0.0
        fit = 0
        for pos, spec in enumerate(rest):
            next_used = used + char_width(spec)
            if next_used > width + FIT_TOLERANCE:
                break
            used = next_used
            fit = pos + 1
        if fit <= 0:
            fit = 1
        if fit >= len(rest):
            chunks.append(list(rest))
            break
        best = None
        floor_pos = max(1, int(fit * 0.4))
        for pos in range(floor_pos, fit + 1):
            if rest[pos - 1][0] in "/.:-_?&=%#":
                best = pos
        cut = best if best else fit
        chunks.append(list(rest[:cut]))
        rest = rest[cut:]
    return chunks


def wrap_specs(specs, width):
    """Wrap char specs into lines fitting width, with kinsoku and word grouping."""
    units = []
    idx, total = 0, len(specs)
    while idx < total:
        ch = specs[idx][0]
        if ch == " ":
            units.append(("space", [specs[idx]]))
            idx += 1
        elif ord(ch) < 128 and ch in ASCII_WORD_CHARS:
            end = idx
            while end < total and ord(specs[end][0]) < 128 and specs[end][0] in ASCII_WORD_CHARS:
                end += 1
            units.append(("word", specs[idx:end]))
            idx = end
        else:
            units.append(("char", [specs[idx]]))
            idx += 1

    # Kinsoku pass 1: closing punctuation glues to the previous unit, opening
    # punctuation glues to the next unit, so neither sits alone at a line edge.
    fused = []
    pending_open = None
    for kind, uspecs in units:
        if kind == "space":
            if pending_open is not None:
                fused.append(("char", pending_open))
                pending_open = None
            fused.append((kind, uspecs))
            continue
        if pending_open is not None:
            uspecs = pending_open + uspecs
            kind = "fused"
            pending_open = None
        elif uspecs[0][0] in NO_LINE_END:
            pending_open = uspecs
            continue
        if uspecs[0][0] in NO_LINE_START and fused and fused[-1][0] != "space":
            fused[-1][1].extend(uspecs)
            continue
        fused.append((kind, uspecs))
    if pending_open is not None:
        fused.append(("char", pending_open))

    # Kinsoku pass 2: over-long units (long URLs) are cut at natural breakpoints.
    expanded = []
    for kind, uspecs in fused:
        if kind != "space" and specs_width(uspecs) > width + FIT_TOLERANCE:
            expanded.extend(("fused", chunk) for chunk in split_long_word(uspecs, width))
        else:
            expanded.append((kind, uspecs))

    lines = []
    cur = []
    cur_w = 0.0
    for kind, uspecs in expanded:
        if kind == "space":
            if cur:
                cur.extend(uspecs)
                cur_w += specs_width(uspecs)
            continue
        unit_w = specs_width(uspecs)

        while cur and cur_w + unit_w > width + FIT_TOLERANCE:
            pending = []
            while len(cur) > 1 and cur[-1][0] in NO_LINE_END:
                pending.insert(0, cur.pop())
            while cur and cur[-1][0] == " ":
                cur.pop()
            if cur:
                lines.append(cur)
            cur = list(pending)
            while cur and cur[0][0] == " ":
                cur.pop(0)
            cur_w = specs_width(cur)

        cur.extend(uspecs)
        cur_w += unit_w

    while cur and cur[-1][0] == " ":
        cur.pop()
    if cur:
        lines.append(cur)
    return [line for line in lines if line]


def line_to_markup(specs, base_size):
    """Render one line of char specs as ReportLab inline markup (tags closed per line)."""
    parts = []
    current_href = None
    current_size = base_size
    for ch, size, href in specs:
        if href != current_href or size != current_size:
            if current_href is not None:
                parts.append("</a>")
            if current_size != base_size:
                parts.append("</font>")
            if size != base_size:
                parts.append('<font size="%g" color="%s">' % (size, URL_COLOR))
            if href is not None:
                parts.append('<a href="%s" color="%s">' % (escape_xml(href), LINK_COLOR))
            current_href, current_size = href, size
        parts.append(escape_xml(ch))
    if current_href is not None:
        parts.append("</a>")
    if current_size != base_size:
        parts.append("</font>")
    return "".join(parts)


def paragraph_markup(text, style, width):
    base_size = style.fontSize
    specs = split_inline(text, base_size)
    lines = wrap_specs(specs, width)
    return "<br/>".join(line_to_markup(line, base_size) for line in lines)


def parse_markdown(markdown):
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks = []
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].strip()
        if not stripped:
            idx += 1
            continue
        if stripped.startswith("|"):
            rows = []
            while idx < len(lines) and lines[idx].strip().startswith("|"):
                rows.append(lines[idx].strip())
                idx += 1
            blocks.append({"kind": "table", "rows": rows})
            continue
        for prefix, kind in (("#### ", "h3"), ("### ", "h3"), ("## ", "h2"), ("# ", "h1")):
            if stripped.startswith(prefix):
                blocks.append({"kind": kind, "text": stripped[len(prefix):].strip()})
                break
        else:
            blocks.append({"kind": "p", "text": stripped})
        idx += 1
    return blocks


def parse_table(rows):
    header = None
    body = []
    for row in rows:
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        if cells and all(TABLE_SEP_RE.match(cell) for cell in cells):
            continue
        if header is None:
            header = cells
        else:
            body.append(cells)
    return header or [], body


def column_widths(header, body, avail_width, cell_size=CELL_SIZE):
    ncols = len(header)
    weights = []
    for col in range(ncols):
        texts = [header[col]] + [row[col] for row in body if col < len(row)]
        longest = max(
            pdfmetrics.stringWidth(specs_plain_text(split_inline(t, cell_size)), FONT_NAME, cell_size)
            for t in texts
        )
        weights.append(longest + 2 * CELL_PAD + 6.0)
    total = sum(weights) or 1.0
    widths = [max(MIN_COL_WIDTH, avail_width * weight / total) for weight in weights]
    scale = avail_width / sum(widths)
    return [width * scale for width in widths]


def build_styles():
    base = ParagraphStyle(
        "Body",
        fontName=FONT_NAME,
        fontSize=BODY_SIZE,
        leading=BODY_LEADING,
        wordWrap="CJK",
        alignment=TA_LEFT,
        spaceAfter=8,
        textColor=colors.HexColor("#1a1a1a"),
    )
    h1 = ParagraphStyle(
        "H1",
        parent=base,
        fontSize=19,
        leading=27,
        alignment=TA_CENTER,
        spaceBefore=0,
        spaceAfter=16,
        textColor=colors.HexColor("#16283c"),
    )
    h2 = ParagraphStyle(
        "H2",
        parent=base,
        fontSize=15,
        leading=21,
        spaceBefore=16,
        spaceAfter=3,
        keepWithNext=1,
        textColor=colors.HexColor("#1f3864"),
    )
    h3 = ParagraphStyle(
        "H3",
        parent=base,
        fontSize=13,
        leading=19,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=1,
        textColor=colors.HexColor("#1f3864"),
    )
    cell = ParagraphStyle("Cell", parent=base, fontSize=CELL_SIZE, leading=CELL_LEADING, spaceAfter=0)
    cellh = ParagraphStyle("CellH", parent=cell, textColor=colors.HexColor("#16283c"))
    return {"base": base, "h1": h1, "h2": h2, "h3": h3, "cell": cell, "cellh": cellh}


def build_table_flowables(rows, styles, avail_width):
    header, body = parse_table(rows)
    ncols = len(header)
    widths = column_widths(header, body, avail_width)
    data = []
    head_cells = [
        Paragraph(paragraph_markup(cell, styles["cellh"], widths[i] - 2 * CELL_PAD), styles["cellh"])
        for i, cell in enumerate(header)
    ]
    data.append(head_cells)
    for row in body:
        row = row + [""] * (ncols - len(row))
        data.append(
            [
                Paragraph(paragraph_markup(cell, styles["cell"], widths[i] - 2 * CELL_PAD), styles["cell"])
                for i, cell in enumerate(row[:ncols])
            ]
        )
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9edf3")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9aa3ad")),
                ("BOX", (0, 0), (-1, -1), 0.9, colors.HexColor("#7d8792")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#7d8792")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD),
                ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD),
                ("TOPPADDING", (0, 0), (-1, -1), 4.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
            ]
        )
    )
    return [Spacer(1, 2), table, Spacer(1, 10)]


def build_story(blocks, styles, avail_width):
    story = []
    for block in blocks:
        kind = block["kind"]
        text = block.get("text", "")
        if kind == "h1":
            story.append(Paragraph(paragraph_markup(text, styles["h1"], avail_width), styles["h1"]))
        elif kind == "h2":
            story.append(Paragraph(paragraph_markup(text, styles["h2"], avail_width), styles["h2"]))
            rule = HRFlowable(
                width="100%", thickness=0.9, color=colors.HexColor("#8ea4c0"), spaceBefore=0, spaceAfter=9
            )
            rule.keepWithNext = 1
            story.append(rule)
        elif kind == "h3":
            story.append(Paragraph(paragraph_markup(text, styles["h3"], avail_width), styles["h3"]))
        elif kind == "p":
            story.append(Paragraph(paragraph_markup(text, styles["base"], avail_width), styles["base"]))
        elif kind == "table":
            story.extend(build_table_flowables(block["rows"], styles, avail_width))
    return story


class NumberedCanvas(pdf_canvas.Canvas):
    """Canvas that draws the running header and 'page X of Y' footers."""

    header_title = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTitle(self.header_title)
        self._saved_states = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._draw_furniture(total)
            super().showPage()
        super().save()

    def _draw_furniture(self, total):
        page = self._pageNumber
        width, height = A4
        self.saveState()
        self.setFont(FONT_NAME, 9)
        self.setFillColor(colors.HexColor("#5b5b5b"))
        self.drawCentredString(width / 2.0, 12 * mm, "第 %d 页 / 共 %d 页" % (page, total))
        if page > 1 and self.header_title:
            self.setFont(FONT_NAME, 8.5)
            self.setFillColor(colors.HexColor("#8a8a8a"))
            self.drawCentredString(width / 2.0, height - 13.2 * mm, self.header_title)
            self.setStrokeColor(colors.HexColor("#d9dee5"))
            self.setLineWidth(0.6)
            self.line(PAGE_MARGIN_X, height - 15.6 * mm, width - PAGE_MARGIN_X, height - 15.6 * mm)
        self.restoreState()


def register_font(font_path=DEFAULT_FONT_PATH, font_index=DEFAULT_FONT_INDEX):
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    if not os.path.exists(font_path):
        raise SystemExit("CJK font not found: %s" % font_path)
    pdfmetrics.registerFont(TTFont(FONT_NAME, font_path, subfontIndex=font_index))


def missing_glyphs(text):
    face = pdfmetrics.getFont(FONT_NAME).face
    return sorted({ch for ch in text if ch not in "\n\r\t" and ord(ch) not in face.charToGlyph})


def build_pdf(input_path, output_path, font_path=DEFAULT_FONT_PATH, font_index=DEFAULT_FONT_INDEX):
    register_font(font_path, font_index)

    with open(input_path, encoding="utf-8") as handle:
        markdown = handle.read()

    missing = missing_glyphs(markdown)
    if missing:
        print(
            "warning: %d characters missing from %s: %s" % (len(missing), FONT_NAME, "".join(missing)),
            file=sys.stderr,
        )

    blocks = parse_markdown(markdown)
    styles = build_styles()
    avail_width = A4[0] - 2 * PAGE_MARGIN_X
    story = build_story(blocks, styles, avail_width)
    title = next((block["text"] for block in blocks if block["kind"] == "h1"), "候选任务书")
    NumberedCanvas.header_title = title

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)

    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        title=title,
        creator="build_pdf.py",
        leftMargin=PAGE_MARGIN_X,
        rightMargin=PAGE_MARGIN_X,
        topMargin=PAGE_MARGIN_TOP,
        bottomMargin=PAGE_MARGIN_BOTTOM,
    )
    frame = Frame(
        PAGE_MARGIN_X,
        PAGE_MARGIN_BOTTOM,
        avail_width,
        A4[1] - PAGE_MARGIN_TOP - PAGE_MARGIN_BOTTOM,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])
    doc.build(story, canvasmaker=NumberedCanvas)

    try:
        from pypdf import PdfReader

        pages = len(PdfReader(output_path).pages)
    except Exception:
        pages = "?"
    print("built %s -> %s; blocks=%d pages=%s" % (input_path, output_path, len(blocks), pages))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Chinese task-book PDF from the candidate markdown.")
    parser.add_argument("paths", nargs="*", metavar="PATH", help="optional [input.md] [output.pdf]")
    parser.add_argument("--input", dest="input_path", default=None, help="source markdown (default: %s)" % DEFAULT_INPUT)
    parser.add_argument("--output", dest="output_path", default=None, help="target pdf (default: %s)" % DEFAULT_OUTPUT)
    parser.add_argument("--font-path", default=DEFAULT_FONT_PATH, help="CJK TTF/TTC font path")
    parser.add_argument("--font-index", type=int, default=DEFAULT_FONT_INDEX, help="subfont index inside a TTC")
    args = parser.parse_args(argv)

    if len(args.paths) > 2:
        parser.error("at most two positional paths: [input] [output]")
    input_path = args.paths[0] if len(args.paths) >= 1 else (args.input_path or DEFAULT_INPUT)
    output_path = args.paths[1] if len(args.paths) >= 2 else (args.output_path or DEFAULT_OUTPUT)

    build_pdf(input_path, output_path, args.font_path, args.font_index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
