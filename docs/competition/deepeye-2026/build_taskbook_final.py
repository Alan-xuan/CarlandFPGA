"""Render the research taskbook with bundled ReportLab; no product execution."""
from pathlib import Path
from html import escape
import re
import hashlib
import json
import argparse
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether


def rich(text):
    text = escape(text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', lambda m: '<link href="'+m.group(2)+'" color="#174A74">'+m.group(1)+'</link>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text


class Taskbook(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ('H1', 'H2'):
            self._outline_counter = getattr(self, '_outline_counter', 0) + 1
            key = 'sec_'+str(self._outline_counter)
            level = 0 if flowable.style.name == 'H1' else 1
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key, level=level, closed=False)


def build(source, output):
    pdfmetrics.registerFont(TTFont('CJK', r'C:\Windows\Fonts\msyh.ttc'))
    pdfmetrics.registerFont(TTFont('CJK-Bold', r'C:\Windows\Fonts\msyhbd.ttc'))
    pdfmetrics.registerFontFamily('CJK', normal='CJK', bold='CJK-Bold', italic='CJK', boldItalic='CJK-Bold')
    styles = {
        'Body': ParagraphStyle('Body', fontName='CJK', fontSize=10.2, leading=15.5, spaceAfter=6, wordWrap='CJK'),
        'Title': ParagraphStyle('Title', fontName='CJK-Bold', fontSize=21, leading=30, spaceAfter=18, wordWrap='CJK'),
        'H1': ParagraphStyle('H1', fontName='CJK-Bold', fontSize=14, leading=21, spaceBefore=14, spaceAfter=8, keepWithNext=True, wordWrap='CJK'),
        'H2': ParagraphStyle('H2', fontName='CJK-Bold', fontSize=11.5, leading=18, spaceBefore=10, spaceAfter=6, keepWithNext=True, wordWrap='CJK'),
        'Cell': ParagraphStyle('Cell', fontName='CJK', fontSize=9, leading=13.5, wordWrap='CJK'),
        'CellHead': ParagraphStyle('CellHead', fontName='CJK-Bold', fontSize=9, leading=13.5, wordWrap='CJK'),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = Taskbook(str(output), pagesize=A4, rightMargin=46, leftMargin=46, topMargin=42, bottomMargin=40, title='矿脉深瞳 FPGA参赛项目任务书', author='CarlandFPGA')
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('CJK', 8)
        canvas.setFillColor(colors.HexColor('#555555'))
        canvas.drawString(46, 22, '矿脉深瞳  2026 FPGA参赛任务书')
        canvas.drawRightString(A4[0]-46, 22, str(doc.page))
        canvas.restoreState()
    doc.addPageTemplates(PageTemplate('all', [frame], onPage=footer))
    lines = source.read_text(encoding='utf-8').splitlines()
    story = []; i=0; paragraph=[]
    def flush():
        if paragraph:
            story.append(Paragraph(rich(' '.join(paragraph)), styles['Body']));paragraph.clear()
    while i<len(lines):
        line=lines[i].strip()
        if not line:
            flush();i+=1;continue
        picture = re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line)
        if picture:
            flush()
            item=Image(str(source.parent/picture.group(2)))
            item.drawHeight=item.imageHeight*doc.width/item.imageWidth
            item.drawWidth=doc.width
            story.append(item);story.append(Spacer(1,8));i+=1;continue
        if line.startswith('|'):
            flush();rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',c) for c in row): rows.append(row)
                i+=1
            n=len(rows[0]); weights=[1.0]*n
            if n==3:weights=[1.15,1.6,2.4]
            elif n==4:weights=[1.0,1.8,2.2,1.8]
            elif n==5:weights=[.8,1.0,1.65,1.8,.8]
            elif n==6:weights=[.75,1.6,1.6,1.7,1.6,1.7]
            widths=[doc.width*w/sum(weights) for w in weights]
            cells=[[Paragraph(rich(c),styles['CellHead' if j==0 else 'Cell']) for c in row] for j,row in enumerate(rows)]
            table=Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E8EDF1')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),.4,colors.HexColor('#87929B')),('INNERGRID',(0,0),(-1,-1),.25,colors.HexColor('#B7BEC4')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            story.append(table);story.append(Spacer(1,8));continue
        if re.match(r'^### H[0-9]{2} ', line):
            flush()
            block=[Paragraph(rich(line[4:]),styles['H2'])]
            i+=1;body=[]
            def flush_block():
                if body:
                    block.append(Paragraph(rich(' '.join(body)),styles['Body']));body.clear()
            while i<len(lines) and not lines[i].strip().startswith('#'):
                if lines[i].strip():body.append(lines[i].strip())
                else:flush_block()
                i+=1
            flush_block();story.append(KeepTogether(block));continue
        if line.startswith('# '):
            flush();story.append(Paragraph(rich(line[2:]),styles['Title']))
        elif line.startswith('## '):
            flush();story.append(Paragraph(rich(line[3:]),styles['H1']))
        elif line.startswith('### '):
            flush();story.append(Paragraph(rich(line[4:]),styles['H2']))
        elif line.startswith('- '):
            flush();story.append(Paragraph('• '+rich(line[2:]),styles['Body']))
        else: paragraph.append(line)
        i+=1
    flush();doc.build(story)
    return {'source':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'output':output.name,'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    print(json.dumps(build(args.source,args.output),ensure_ascii=False))
