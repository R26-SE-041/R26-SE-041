"""Render the consolidated BioLearnX group deployment report and QA previews."""
from pathlib import Path
import html
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp/pdfs/deployment-runtime'))
import pymupdf
from PIL import Image as PILImage, ImageDraw
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, NextPageTemplate, KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents

SOURCE = ROOT / 'deployment-reports/BioLearnX_Group_Deployment_Report.md'
TARGET = ROOT / 'output/pdf/R26-SE-041_BioLearnX_Deployment_Report.pdf'
QA = ROOT / 'tmp/pdfs/group-deployment-report'
QA.mkdir(parents=True, exist_ok=True)
TARGET.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('GroupTimes', 'C:/Windows/Fonts/times.ttf'))
pdfmetrics.registerFont(TTFont('GroupTimes-Bold', 'C:/Windows/Fonts/timesbd.ttf'))
pdfmetrics.registerFontFamily('GroupTimes', normal='GroupTimes', bold='GroupTimes-Bold', italic='GroupTimes', boldItalic='GroupTimes-Bold')
WIDTH = A4[0]-144
STYLES = {
 'body': ParagraphStyle('body',fontName='GroupTimes',fontSize=12,leading=18,spaceAfter=9,alignment=TA_JUSTIFY,allowOrphans=0,allowWidows=0),
 'h1': ParagraphStyle('h1',fontName='GroupTimes-Bold',fontSize=14,leading=21,spaceAfter=16,keepWithNext=True),
 'h2': ParagraphStyle('h2',fontName='GroupTimes-Bold',fontSize=12,leading=18,spaceBefore=10,spaceAfter=9,keepWithNext=True),
 'h3': ParagraphStyle('h3',fontName='GroupTimes-Bold',fontSize=12,leading=18,spaceBefore=8,spaceAfter=8,keepWithNext=True),
 'cell': ParagraphStyle('cell',fontName='GroupTimes',fontSize=10.5,leading=14,alignment=TA_LEFT),
 'center': ParagraphStyle('center',fontName='GroupTimes',fontSize=18,leading=25,alignment=TA_CENTER,spaceAfter=12),
 'cover_title': ParagraphStyle('cover_title',fontName='GroupTimes',fontSize=14,leading=20,alignment=TA_CENTER,spaceAfter=14),
}


def markup(text):
    text=html.escape(text.replace('—','-').replace('–','-').replace('‑','-'))
    return re.sub(r'`([^`]+)`',r'<font name="Courier" size="9.2">\1</font>',text)


def para(text,style='body'):
    return Paragraph(markup(text),STYLES[style])


def grid(rows,widths=None):
    widths=widths or ([WIDTH*.31,WIDTH*.69] if len(rows[0])==2 else [WIDTH*.24,WIDTH*.38,WIDTH*.38])
    cells=[]
    for i,row in enumerate(rows):
        cells.append([Paragraph(('<b>'+markup(x)+'</b>') if i==0 else markup(x),STYLES['cell']) for x in row])
    table=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.45,colors.HexColor('#777777')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
    return table


class Report(BaseDocTemplate):
    def __init__(self):
        super().__init__(str(TARGET),pagesize=A4,leftMargin=72,rightMargin=72,topMargin=66,bottomMargin=60,title='BioLearnX - Group Deployment Report - R26-SE-041',author='Kojithan P. Y; Baskaran V; Nishara T; Sarmitha S')
        frame=Frame(72,60,WIDTH,A4[1]-126,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates([PageTemplate(id='front',frames=[frame],onPage=self.front),PageTemplate(id='body',frames=[frame],onPage=self.body)])

    def beforeDocument(self):
        self.body_start=None
        self.headings=[]

    def decorate(self,canvas,number):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#777777'));canvas.setLineWidth(.5)
        canvas.rect(24,24,A4[0]-48,A4[1]-48)
        canvas.setFont('GroupTimes',10)
        canvas.drawCentredString(A4[0]/2,38,str(number))
        canvas.restoreState()

    def front(self,canvas,doc):
        self.decorate(canvas,self.page)

    def body(self,canvas,doc):
        if self.body_start is None:self.body_start=self.page
        self.decorate(canvas,self.page-self.body_start+1)

    def afterFlowable(self,flowable):
        if not isinstance(flowable,Paragraph) or flowable.style.name not in ['h1','h2','h3']:return
        title=flowable.getPlainText()
        if not re.match(r'^\d+\.',title):return
        level={'h1':0,'h2':1,'h3':2}[flowable.style.name]
        key='section-'+str(len(self.headings))
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title,key,level=level,closed=False)
        page=self.page-self.body_start+1
        self.notify('TOCEntry',(level,title,page,key))
        self.headings.append({'title':title,'body_page':page,'physical_page':self.page})


text=SOURCE.read_text(encoding='utf-8')
leakage=[r'\bthis report\b',r'\bsenior\b',r'\bsample\b',r'\bsource[- ]based\b',r'\brepository review\b',r'\breport preparation\b',r'\bnot (?:measured|collected|checked)\b',r'\binspected checkout\b',r'\boperator confirmation\b',r'\bplaceholder\b',r'\btemplate\b',r'\bTODO\b',r'\b(?:I|we) (?:have|will|reviewed|checked|generated)\b',r'\b(?:as requested|for this report|during preparation|formatting reference|editorial leakage|meta.commentary)\b']
# "Environment templates" are operational files, so only authoring-template wording is prohibited.
leakage.remove(r'\btemplate\b')
for pattern in leakage:
    if re.search(pattern,text,re.I):raise RuntimeError('Editorial content found: '+pattern)

logo=ROOT/'tmp/pdfs/deployment-reports-sample-style/sliit-logo.png'
if not logo.exists():raise FileNotFoundError('SLIIT cover logo is missing')
cover=[Paragraph('Research Project<br/>(Comprehensive Design and Analysis Project)',STYLES['center']),Spacer(1,8),para('IT4010','center'),Spacer(1,20),Image(str(logo),width=126,height=126),Spacer(1,24),para('BIOLEARNX: A MULTIMODAL, MULTI-AGENT FRAMEWORK FOR PERSONALIZED BIOLOGY LEARNING','cover_title'),Spacer(1,8),para('Deployment Report','center'),Spacer(1,32),para('Group Details','h3'),para('Group No: R26-SE-041'),grid([['Student ID','Student Name'],['IT22264220','Kojithan P. Y'],['IT22172600','Baskaran V'],['IT22223876','Nishara T'],['IT22637482','Sarmitha S']]),PageBreak()]
toc=TableOfContents()
toc.levelStyles=[ParagraphStyle('toc0',fontName='GroupTimes',fontSize=11,leading=15,leftIndent=0,spaceBefore=5),ParagraphStyle('toc1',fontName='GroupTimes',fontSize=10.5,leading=14,leftIndent=12,spaceBefore=2),ParagraphStyle('toc2',fontName='GroupTimes',fontSize=10,leading=13,leftIndent=24,spaceBefore=1)]
toc.dotsMinLevel=0
story=cover+[Paragraph('TABLE OF CONTENTS',ParagraphStyle('toc_title',fontName='GroupTimes-Bold',fontSize=14,leading=21,alignment=TA_CENTER,spaceAfter=14)),toc,NextPageTemplate('body'),PageBreak()]
body=text[text.index('## 1. DEPLOYMENT OVERVIEW'):].splitlines()
i=0
while i<len(body):
    line=body[i].strip()
    if not line:i+=1;continue
    if line.startswith('## '):
        if not line.startswith('## 1.'):story.append(PageBreak())
        story.append(para(line[3:],'h1'))
    elif line.startswith('### '):story.append(para(line[4:],'h2'))
    elif line.startswith('#### '):story.append(para(line[5:],'h3'))
    elif line.startswith('|'):
        rows=[]
        while i<len(body) and body[i].strip().startswith('|'):
            cells=[c.strip() for c in body[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r'[-: ]+',c) for c in cells):rows.append(cells)
            i+=1
        table=grid(rows)
        if table.wrap(WIDTH,700)[1]<360:
            group=[table,Spacer(1,12)]
            if isinstance(story[-1],Paragraph) and story[-1].style.name in ['h1','h2','h3']:
                group.insert(0,story.pop())
            story.append(KeepTogether(group))
        else:story.append(table)
        continue
    elif line.startswith('- '):
        style=ParagraphStyle('bullet',parent=STYLES['body'],leftIndent=18,bulletIndent=2,spaceAfter=7)
        items=[]
        while i<len(body) and body[i].strip().startswith('- '):
            items.append(Paragraph(markup(body[i].strip()[2:]),style,bulletText='\u2022'))
            i+=1
        if isinstance(story[-1],Paragraph) and story[-1].style.name in ['h1','h2','h3']:
            items.insert(0,story.pop())
        story.append(KeepTogether(items));continue
    else:story.append(para(line))
    i+=1
doc=Report();doc.multiBuild(story)
pdf=pymupdf.open(TARGET)
full_text='\n'.join(p.get_text() for p in pdf)
for pattern in leakage:
    if re.search(pattern,full_text,re.I):raise RuntimeError('Editorial content in final PDF: '+pattern)
for item in doc.headings:
    page_text=' '.join(pdf[item['physical_page']-1].get_text().split())
    if ' '.join(item['title'].split()) not in page_text:raise RuntimeError('Contents mapping mismatch: '+item['title'])
for identifier in ['IT22264220','IT22172600','IT22223876','IT22637482','R26-SE-041']:
    if identifier not in pdf[0].get_text():raise RuntimeError('Missing group cover detail: '+identifier)
thumbnails=[]
for index,page in enumerate(pdf):
    for b in page.get_text('blocks'):
        if b[0]<23 or b[2]>A4[0]-23 or b[1]<23 or b[3]>A4[1]-23:raise RuntimeError(f'Out-of-bounds text on page {index+1}')
    path=QA/f'page-{index+1:02}.png'
    page.get_pixmap(matrix=pymupdf.Matrix(1.25,1.25),alpha=False).save(path)
    image=PILImage.open(path).convert('RGB');image.thumbnail((400,566));thumbnails.append(image)
for offset in range(0,len(thumbnails),4):
    group=thumbnails[offset:offset+4]
    sheet=PILImage.new('RGB',(820,((len(group)+1)//2)*595),'#DDDDDD');draw=ImageDraw.Draw(sheet)
    for index,image in enumerate(group):
        x=(index%2)*410+5;y=(index//2)*595+20;sheet.paste(image,(x,y));draw.text((x,y-15),f'Page {offset+index+1}',fill='black')
    sheet.save(QA/f'contact-{offset//4+1:02}.png')
summary={'file':str(TARGET),'pages':len(pdf),'body_start':doc.body_start,'words':len(text.split()),'headings':doc.headings,'editorial_scan':'passed','contents_mapping':'passed','cover_details':'passed','text_bounds':'passed'}
(QA/'validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(QA/'extracted-text.txt').write_text(full_text,encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='headings'},indent=2))
