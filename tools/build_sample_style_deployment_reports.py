"""Typeset four deployment reports using the supplied senior report's structure."""
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
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, NextPageTemplate
from reportlab.platypus.tableofcontents import TableOfContents

OUT = ROOT / 'output/pdf'
QA = ROOT / 'tmp/pdfs/deployment-reports-sample-style'
SOURCES = ROOT / 'deployment-reports/sample-style'
for path in [OUT, QA, SOURCES]:
    path.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('TNR', 'C:/Windows/Fonts/times.ttf'))
pdfmetrics.registerFont(TTFont('TNR-Bold', 'C:/Windows/Fonts/timesbd.ttf'))
pdfmetrics.registerFontFamily('TNR', normal='TNR', bold='TNR-Bold', italic='TNR', boldItalic='TNR-Bold')
sample = pymupdf.open('C:/Users/Koji/Downloads/Deployment_Report_25-26J-434 3.pdf')
logo = QA / 'sliit-logo.png'
logo.write_bytes(sample.extract_image(sample[0].get_images(full=True)[0][0])['image'])
sample.close()

WIDTH = A4[0] - 144
styles = {
    'body': ParagraphStyle('body', fontName='TNR', fontSize=12, leading=17, alignment=TA_JUSTIFY, spaceAfter=8, allowOrphans=0, allowWidows=0),
    'h1': ParagraphStyle('h1', fontName='TNR-Bold', fontSize=14, leading=21, spaceAfter=16, keepWithNext=True),
    'h2': ParagraphStyle('h2', fontName='TNR-Bold', fontSize=12, leading=18, spaceBefore=10, spaceAfter=10, keepWithNext=True),
    'h3': ParagraphStyle('h3', fontName='TNR-Bold', fontSize=12, leading=18, spaceBefore=8, spaceAfter=8, keepWithNext=True),
    'cell': ParagraphStyle('cell', fontName='TNR', fontSize=10, leading=13, alignment=TA_LEFT),
    'code': ParagraphStyle('code', fontName='Courier', fontSize=8.2, leading=12, alignment=TA_LEFT),
    'center': ParagraphStyle('center', fontName='TNR', fontSize=18, leading=24, alignment=TA_CENTER, spaceAfter=12),
    'cover_title': ParagraphStyle('cover_title', fontName='TNR', fontSize=14, leading=20, alignment=TA_CENTER, spaceAfter=14),
    'note': ParagraphStyle('note', fontName='TNR', fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=8),
}

CONFIG = {
 '01-koji': dict(member='Kojithan P. Y', sid='IT22264220', title='INTERACTIVE INFOGRAPHIC GENERATION',
    directory='koji-interactive-infographic-generator',
    overview='The interactive visualization component provides prompt-to-image and sketch-to-image generation, biology anatomy diagrams, editable labels, region-based questions, persistent learning history, and optional 3D conversion. It separates CPU application services from GPU inference so that learning requests can be queued and completed independently of the browser session.',
    purpose='The deployment supports evaluation of a complete visual learning workflow, including authenticated access, durable execution, model integration, private asset storage, and recovery after process interruption. Its purpose is to verify that the visualization interface and independently hosted services operate as one reproducible component.',
    initialization='The API and worker share the existing Supabase project and backend configuration. Required schema changes are applied with python -m studio.migrate before code that depends on them is released. The AWS activation process does not apply migrations. Component-owned job, history, document and chunk tables, pgvector support, and private storage must be available for the selected features.',
    metrics=[('API and worker availability','API /health and /ready, service status, and job processing progress.'),('Job completion and queue delay','Submitted, completed and failed jobs; queue waiting time and lease recovery.'),('Model response time','Cold and warm inference duration, retries and endpoint failures.'),('Retrieval and storage integrity','Owner-scoped sources, private asset access, and saved history consistency.')],
    scenarios=[('Prompt and sketch generation','Sign in, submit a prompt and a sketch, wait for durable jobs, and inspect generated output and labels.','A completed result and corresponding history event are available without requiring the original browser tab to remain open.'),('Label editing and conversation recovery','Change labels, reopen a conversation after browser refresh, and export the supported labeled result.','Edited labels and linked generation versions remain associated with the correct account and image.'),('PDF-grounded image questions','Upload a representative text PDF, select it for a region question, and inspect cited passages. Repeat with a second account.','Sources belong to the signed-in owner and selected documents; missing evidence is reported explicitly.'),('Worker restart and optional 3D conversion','Restart the worker during a controlled job and run a 3D conversion where its endpoint is configured.','Job recovery follows the implemented lease/call-handle behavior and saved GLB output remains linked to its source.')],
    issues=[('Release configuration is installation-dependent','Receiver control files, deployment tokens, production switches and origin values need operator confirmation.','Verify the installed receiver and protected environment before enabling automatic release.'),('Schema and agent compatibility','PDF features require matching migrations and an interactive agent that accepts the new context fields.','Apply reviewed migrations first and release the dependent agent/API/client together.'),('Model cache and endpoint changes','CPU PDF embeddings need a cache; queued jobs preserve their captured model URLs.','Persist cache files, record endpoint versions, and distinguish existing jobs from new jobs after configuration changes.')],
    lessons=['A persistent worker is necessary for long-running model jobs and browser-independent completion.','Frontend, CPU API and GPU agents benefit from independent releases with explicit compatibility checks.','Database readiness, account isolation and model-output behavior require separate acceptance evidence.']),
 '02-baskaran': dict(member='Baskaran V', sid='IT22172600', title='MULTILINGUAL INTERACTIVE AUDIO COMMUNICATION',
    directory='baskaran-interactive-audio-communication',
    overview='VoiceLearn enables students to ask voice questions about uploaded lecture material and receive retrieval-grounded answers with language-specific speech output. The component combines a Next.js interface, a FastAPI application, Supabase identity and storage, ChromaDB retrieval, and separately deployed Modal speech and language services.',
    purpose='The deployment supports evaluation of the complete document-to-voice learning experience across English, Tamil and Sinhala. Its purpose is to verify document ingestion, transcription, answer generation, audio playback, persistence and controlled fallback behavior under the selected language configuration.',
    initialization='The database and storage environment must contain the required Supabase tables, row-level policies and private document/audio buckets. API startup attempts schema creation through an exec_sql RPC, but errors are non-fatal. Operators must verify the actual schema rather than interpreting successful startup as proof that migrations succeeded. ChromaDB must retain its index and remain reachable from the API.',
    metrics=[('API and retrieval availability','API /health, Chroma connectivity and successful source retrieval.'),('Speech-processing latency','Cold/warm ASR, transcript correction and TTS response durations by language.'),('Document ingestion behavior','Accepted files, indexing duration, failed ingestion and cache availability.'),('Answer and audio completeness','Grounded answers, enabled TTS output, revision downloads and persistent history.')],
    scenarios=[('Document upload and grounded questions','Sign in, upload a lecture document and ask a question requiring its content. Repeat using an unrelated question.','The answer follows the document-based workflow and private documents remain isolated by owner.'),('Multilingual voice input','Submit English, Tamil and Sinhala recordings through their configured ASR routes.','The selected route returns usable transcription or an explicit controlled failure/fallback.'),('Speech output and revision playback','Enable and test the applicable TTS routes; generate revision audio and inspect download/playback controls.','Audio is playable for enabled languages and a text response remains understandable when TTS is unavailable.'),('Persistence and service failure','Restart the API/index, reopen history and simulate an unavailable model URL in a test environment.','Persisted documents/history survive restart and errors are visible without silently losing learner state.')],
    issues=[('Frontend container requires a prior build','The Dockerfile copies .next/standalone instead of creating it.','Run the validated production Next.js build before building the runner image.'),('Compose defaults need production adjustment','The client URL points to localhost and the API has a development source mount.','Configure the public API during the frontend build and prepare a production override without the development mount.'),('Health-check tooling and model artifacts','Compose checks call curl; the backend Dockerfile does not explicitly install it. Gemma expects a populated model volume.','Verify/install the health-check executable and provision the base weights and V2 adapter before acceptance.')],
    lessons=['Language-specific endpoint selection must be checked against current routing code rather than an older model overview.','Prebuilt frontend variables and backend runtime variables have different release behavior.','Liveness does not establish retrieval quality, migration success or audio completeness.']),
 '03-nishy': dict(member='Nishara T', sid='IT22223876', title='ADAPTIVE QUIZ GENERATION AND RECOMMENDATION',
    directory='nishy-adaptive-quiz-recommender',
    overview='The adaptive assessment component converts learning documents into grounded quizzes, evaluates submitted answers, adjusts question difficulty, and produces analytics and topic recommendations. A LangGraph workflow coordinates the agents, while SQLite stores learner-session data and checkpoints and ChromaDB stores document embeddings.',
    purpose='The deployment supports assessment of a complete document-to-quiz workflow, including generation, evaluation, adaptation, hints, recommendations and session recovery. Its purpose is to establish reproducible operation of the CPU application with the fine-tuned Qwen Modal service and persistent local data.',
    initialization='The backend requires writable session and checkpoint database directories, an upload location and a persistent Chroma index. The graph compiles during application startup, and database service initialization creates tables and applies additive migrations. Existing state must be backed up before schema-changing releases. A single backend process is the initial deployment arrangement because multi-replica session and local-state behavior has not been demonstrated.',
    metrics=[('API and generation availability','API /health, Modal generation failures and complete quiz requests.'),('Quiz processing time','Document ingestion, question generation, hints and answer-evaluation latency.'),('Grounding and adaptive behavior','Source support, answer-type handling, difficulty changes and recommendations.'),('Session persistence','Session database, checkpoints, uploads and retrieval index after restart.')],
    scenarios=[('Document ingestion and grounded quiz','Upload a supported document, create a session and inspect generated questions with their source context.','Questions follow the supplied material and rejected/unsupported generation is handled explicitly.'),('MCQ and open-ended evaluation','Submit correct and incorrect examples for both supported answer types and inspect feedback.','Evaluation is returned through the intended route and the session records the submitted answer.'),('Adaptation, hints and recommendations','Advance through questions with different performance patterns, request hints and view final recommendations.','Difficulty and recommendations reflect the implemented session logic, with usable learner feedback.'),('Restart, checkpoints and model timeout','Restart during an isolated session and simulate an unavailable model endpoint.','Session/checkpoint state is retained and model failure produces an understandable outcome.')],
    issues=[('Frontend API module is missing','Quiz/upload/result pages import @/lib/api, which is absent in the inspected checkout.','Restore or implement the module against the backend contracts, then pass TypeScript and production build checks.'),('Production hosting and automation are not evidenced','No component-specific Dockerfile, hosting manifest or root release workflow was found.','Record the selected persistent host and establish a reproducible release procedure before sign-off.'),('Local state and dependency compatibility','SQLite/Chroma persistence and LangGraph checkpoint package compatibility need clean-environment validation.','Use one worker initially, validate installed packages and test coordinated backup/restore.')],
    lessons=['Persistent state is part of the assessment deployment, not an incidental local development file.','A static health response must be complemented by a complete quiz and evaluation scenario.','Horizontal scaling requires shared-state and background-work design beyond the current single-instance setup.']),
 '04-sarmitha': dict(member='Sarmitha S', sid='IT22637482', title='INTELLIGENT IMAGE-TO-TEXT AND STUDY NOTE GENERATION',
    directory='sarmitha-image-text-extractor-study-gen',
    overview='The image-to-notes component enhances handwritten images, extracts Sinhala text, translates the result into Tamil and English, and collects corrected OCR crops for future model training. The FastAPI CPU application invokes independent Modal enhancement, OCR and translation endpoints and returns text, line information and comparison images to an Expo interface.',
    purpose='The deployment supports evaluation of handwritten-image processing as a usable biology learning aid. Its purpose is to validate model connectivity, accepted upload handling, OCR cleanup, translation completeness, feedback retention and interface integration without treating optional correction agents as active in the current route.',
    initialization='The CPU backend loads endpoint URLs and allowed origins from its environment. The current /api/process route creates enhancement output for comparison but sends the original image bytes to line-level TrOCR extraction. It then cleans Sinhala output and translates it sequentially. SinhaLM/Qwen visual context correction is skipped by this route. A writable persistent backend/dataset directory is needed when retaining learner corrections.',
    metrics=[('API and endpoint availability','Root API response and successful enhancement/OCR/translation calls.'),('Processing latency','Cold/warm model duration and total image processing time.'),('Output completeness','Sinhala text, line confidence/crops, enhancement image and both translations.'),('Feedback persistence and input handling','Retained corrections, supported media types, rejected oversized inputs and disk growth.')],
    scenarios=[('Sinhala handwritten-image processing','Submit a representative accepted image to /api/process and inspect returned images and line-level text.','OCR uses original image bytes and returns cleaned Sinhala output with comparison data.'),('Tamil and English translation','Process a meaningful Sinhala sample and inspect both translation fields, including a controlled translation failure.','Both translations contain usable output when their service succeeds; empty fields are detected during acceptance.'),('Upload validation and failure behavior','Submit an unsupported media type, an oversized upload and a request with an unavailable model URL.','The API rejects invalid input and returns an identifiable configuration/inference error.'),('Correction feedback and restart','Save an isolated crop correction through /api/feedback/ocr, then restart and inspect images and metadata.','The crop and matching JSONL entry survive restart in the persistent dataset location.')],
    issues=[('Frontend API module is missing','The Expo screen imports @/lib/api, absent from the inspected checkout.','Restore its types, upload handling and configurable HTTPS origin, then validate install/export.'),('Translation may be incomplete without total request failure','The processing route catches translation errors and can return empty language fields.','Check both translated fields explicitly and retain a visible partial-result handling policy.'),('Local feedback and public-access configuration','Feedback writes local JSONL and timestamp-based filenames; inspected routes have no application authentication.','Use one worker initially, persist the dataset and configure access appropriate to the intended deployment audience.')],
    lessons=['Model filenames and comments can lag behind the active implementation; the enhancement service now uses Swin2SR.','A successful processing response does not guarantee complete translation output.','Feedback datasets require durable storage and release procedures that preserve training material.']),
}


def clean(text):
    return text.replace('—','-').replace('–','-').replace('‑','-')


def markup(text):
    text = clean(text)
    links=[]
    def link(match):
        label,target=match.groups()
        if not target.startswith('https://'):
            target=(ROOT/'deployment-reports'/target).resolve().relative_to(ROOT).as_posix()
            target='https://github.com/R26-SE-041/R26-SE-041/blob/main/'+target
        links.append((label,target))
        return f'PDFLINK{len(links)-1}TOKEN'
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, text)
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    for index,(label,target) in enumerate(links):
        text=text.replace(f'PDFLINK{index}TOKEN',f'<a href="{html.escape(target,quote=True)}"><u>{html.escape(label)}</u></a>')
    return text


def para(text, style='body'):
    return Paragraph(markup(text), styles[style])


def grid(rows, widths=None):
    n = len(rows[0])
    widths = widths or ([WIDTH*.36, WIDTH*.64] if n == 2 else [WIDTH/n]*n)
    data = [[para(value, 'cell') for value in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.45,colors.HexColor('#777777')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
    return t


class Report(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, pagesize=A4, leftMargin=72, rightMargin=72, topMargin=66, bottomMargin=60, **kwargs)
        self.body_start = None
        self.headings = []
        frame = Frame(72,60,WIDTH,A4[1]-126,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates([PageTemplate(id='front',frames=[frame],onPage=self.front_page),PageTemplate(id='body',frames=[frame],onPage=self.body_page)])

    def decoration(self, canvas, number):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#777777'))
        canvas.setLineWidth(.5)
        canvas.rect(24,24,A4[0]-48,A4[1]-48)
        canvas.setFont('TNR',10)
        canvas.drawCentredString(A4[0]/2,38,str(number))
        canvas.restoreState()

    def front_page(self, canvas, doc):
        self.decoration(canvas, self.page)

    def body_page(self, canvas, doc):
        if self.body_start is None:
            self.body_start = self.page
        self.decoration(canvas, self.page-self.body_start+1)

    def beforeDocument(self):
        self.body_start = None
        self.headings = []

    def afterFlowable(self, flowable):
        if isinstance(flowable,Paragraph) and (flowable.style.name in ['h1','h2'] or (flowable.style.name=='h3' and flowable.getPlainText().startswith('2.5.'))):
            level = 0 if flowable.style.name == 'h1' else (2 if flowable.style.name=='h3' else 1)
            title = flowable.getPlainText()
            page = self.page-self.body_start+1 if self.body_start else self.page
            key = 'section-'+str(len(self.headings))
            self.canv.bookmarkPage(key)
            self.notify('TOCEntry',(level,title,page,key))
            self.headings.append((title,page))


def original_blocks(text):
    result=[]
    lines=text.splitlines()
    i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:
            i+=1; continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+',c) for c in cells): rows.append(cells)
                i+=1
            result.append(('table',rows)); continue
        if line.startswith('```'):
            i+=1; code=[]
            while i<len(lines) and not lines[i].strip().startswith('```'):
                code.append(lines[i].strip());i+=1
            result.append(('code','\n'.join(code)))
        else: result.append(('p',line))
        i+=1
    return result


def build_content(key,c):
    source=next((ROOT/'deployment-reports').glob(key+'-deployment-report.md')).read_text(encoding='utf-8')
    sections={int(n):body.strip() for n,body in re.findall(r'^## (\d+)\. [^\n]+\n(.*?)(?=^## |\Z)',source,re.M|re.S)}
    blocks=[]
    def add(kind,text): blocks.append((kind,text))
    def heading(text): add('h2',text)
    def p(text): add('p',text)
    def chapter(text):
        if blocks: add('break','')
        add('h1',text)
    chapter('1. DEPLOYMENT OVERVIEW')
    heading('1.1 Overview')
    p(c['overview'])
    for kind,text in original_blocks(sections[1])[1:]: add(kind,text)
    heading('1.2 Purpose of the Deployment')
    p(c['purpose'])
    p('A repeatable deployment must connect the interface, application services, model inference and persistent data while retaining the configuration and evidence required to reproduce the release. The assessment therefore considers both installation correctness and the learner-facing workflow.')
    heading('1.3 Scope of the Deployment')
    p('This report covers the '+c['title'].lower()+' component only. The shared learning interface, research website and other three research components retain their own deployment responsibilities. The scope includes environment preparation, model endpoint configuration, application release, secure service access, verification, backup and recovery.')
    p('The report is based on the inspected project repository. Hosting already documented in source is identified separately from proposed installation steps. No new cloud release, paid inference or production database migration was executed during preparation. Runtime acceptance results require a release-specific evidence record.')
    heading('1.4 Key Metrics Monitored')
    p('The following metrics define the operational monitoring plan for deployment evaluation. They are selected from the component workflow and should be collected during a controlled acceptance run; measured values are not supplied in the available deployment evidence.')
    add('table',[['Metric','Description']]+[list(row) for row in c['metrics']])
    heading('1.5 Deployment Success Metrics')
    p('Deployment success is evaluated against installation, integration and learner workflow criteria. Health checks alone are insufficient because an API can answer a liveness request while a model, database, index or private storage service remains unavailable.')
    add('table',[['Indicator','Acceptance criterion'],['Service initialization','Required processes start with the selected environment and no unresolved startup failure.'],['Configuration consistency','Frontend origin, API URL, model endpoints and persistent paths match the release record.'],['Functional completeness','All mandatory component scenarios produce the expected outcomes.'],['Data persistence','Required learner state and files remain available after a controlled restart.'],['Recovery readiness','A compatible previous release and tested backup procedure are identified.']])
    heading('1.6 Success Rate and Error Monitoring')
    p('For a release trial, calculate deployment success rate as successfully verified required services divided by all required services, multiplied by 100. Calculate workflow error rate from failed requests divided by total observed requests over the same recorded test interval. Keep configuration failures, model failures and invalid-input rejections separate so that expected rejection behavior is not mistaken for an outage.')
    p('No measured deployment percentage or incident trend is asserted here. The release record must identify the test period, number of requests, endpoint/model revisions, and observed failures before reporting quantitative results.')
    heading('1.7 Key Outcomes of the Deployment')
    p('The repository review establishes the component architecture, required configuration, release dependencies, verification scenarios and recovery requirements. A completed deployment should demonstrate a usable '+c['title'].lower()+' workflow and durable handling of the component data described below. Operational success remains subject to the acceptance criteria and pending items identified in this report.')

    chapter('2. DEPLOYMENT PROCESS')
    p('The deployment process follows environment preparation, initialization, application/model release, access configuration and scenario-based verification. The steps are specific to this component and preserve its actual hosting and storage architecture.')
    heading('2.1 Deployment Environment Preparation')
    for kind,text in original_blocks(sections[2]): add(kind,text)
    p('Select the release commit and install dependencies in an isolated environment. Record the actual operating system, runtime versions, host allocation, storage mapping and public endpoints. CPU/RAM specifications and concurrent-user capacity should be taken from the selected host and measurements rather than assumed from the presence of deployment scripts.')
    heading('2.2 Service and Data Initialization')
    p(c['initialization'])
    heading('2.3 Deployment of System Components')
    p('Configure application and model services using the following repository-supported variables and deployment sequence. Commands use a Linux deployment shell unless a PowerShell helper is explicitly identified.')
    for kind,text in original_blocks(sections[3]): add(kind,text)
    for kind,text in original_blocks(sections[4]): add(kind,text)
    heading('2.4 Secure Access Configuration')
    p('The hosted browser interface and API require compatible HTTPS endpoints and exact permitted frontend origins. Private credentials belong in the backend or deployment-secret store. Public frontend variables may contain the API origin and public identity key, but must not contain database passwords, service-role credentials or private deployment tokens.')
    p('Restrict internal process and database/index ports to the required application network. Access control must match the intended audience and be verified independently of CORS. Record how an administrator inspects logs and restarts the service using the tools selected for this component.')
    heading('2.5 Execution of Testing Scenarios')
    p('Execute the following component-specific scenarios using isolated test accounts, representative source material and a recorded release configuration. The descriptions are acceptance procedures, not claims that the scenarios have already passed.')
    for i,(title,action,expected) in enumerate(c['scenarios'],1):
        add('h3',f'2.5.{i} Scenario {i} - {title}')
        p('Test procedure: '+action)
        p('Expected behavior: '+expected)
        p('Evidence to retain: request/test identifier, relevant screenshot or response, timestamps, service/model version and the observed pass/fail outcome.')
    heading('2.6 Backup and Recovery Strategy')
    for kind,text in original_blocks(sections[6]): add(kind,text)
    heading('2.7 Deployment Details')
    add('table',[['Deployment item','Recorded arrangement'],['Research project','BioLearnX / R26-SE-041'],['Component owner',c['member']+' / '+c['sid']],['Source directory',c['directory']+'/'],['Release identification','Repository commit and application/model artifact versions to be recorded at release.'],['Environment evidence','Documented source configuration; live installation details require operator confirmation.'],['Execution mode','Independent component deployment and scenario-based acceptance.']])
    heading('2.8 Deployment Checklist')
    for phase,items in [('Pre-Deployment',['Select and record the release commit.','Resolve the component-specific pending installation items.','Verify dependency installation, secrets, origins and endpoint URLs.','Prepare persistent storage and a consistent backup.']),('During Deployment',['Initialize required schema/index/model artifacts.','Deploy compatible model and application versions.','Apply HTTPS routing and exact frontend-origin configuration.','Verify startup logs and required process status.']),('Post-Deployment',['Run component scenarios and record observed results.','Verify persistence and intended data-access boundaries.','Review cold-start errors, timeouts and partial outputs.','Confirm rollback target and update the release record.'])]:
        add('h3',phase)
        for item in items: add('bullet',item)
    heading('2.9 Deployment Verification and Completion')
    p('Deployment is complete only when required services and dependencies are reachable, the interface uses the intended API, persistent storage is retained, and mandatory scenarios pass with evidence. Record any unresolved issue as a release limitation. The current report provides a verification procedure and source-based readiness assessment; it does not replace operator sign-off.')

    chapter('3. ISSUES, RESOLUTION, AND MONITORING')
    heading('3.1 Issues Encountered During Deployment Review')
    p('The following items were identified from source inspection and configuration review. They are confirmed repository/deployment requirements, rather than invented incidents from a live installation.')
    for i,(issue,detail,resolution) in enumerate(c['issues'],1):
        add('h3',f'Issue {i}: {issue}'); p(detail)
    heading('3.2 Resolutions and Required Actions')
    for i,(issue,detail,resolution) in enumerate(c['issues'],1):
        add('h3',f'Resolution for Issue {i}');p(resolution)
    p('These actions must be verified in the release environment. Their presence in this report does not mean the corresponding source code, host configuration or production installation was modified during report preparation.')
    heading('3.3 Impact Analysis')
    p('Configuration and build gaps can prevent a usable client release even when individual backend services exist. Missing model artifacts or mismatched endpoints can interrupt inference, while incomplete persistence can cause learner state or feedback loss after restart. The listed actions address these concrete release dependencies. No outage duration, user count or production incident severity is inferred without a live record.')
    heading('3.4 Monitoring and System Observability')
    p('Collect application logs, process status, model-platform logs and persistent-storage usage for the selected deployment. Correlate API and model events using request/job/session identifiers wherever available. Inspect both total request duration and individual processing stages, since a slow or unavailable dependency can be hidden by an otherwise responsive API.')
    p('Use the metrics in Section 1.4 for a consistent monitoring record. Separate startup/liveness checks from full workflow checks, and retain cold-start observations alongside warm-request behavior. No additional monitoring dashboard is claimed to be installed by this report.')
    heading('3.5 Monitoring Results')
    add('table',[['Result category','Evidence status'],['Repository architecture and configuration','Reviewed and described in this report.'],['Live process uptime and dependency health','Not measured during report preparation.'],['Workflow latency and error rate','Requires a recorded acceptance run.'],['Backup restoration and runtime recovery','Requires verification in an isolated environment.']])
    heading('3.6 User Feedback')
    p('No new deployment user-feedback study was supplied or conducted for this report. Collect feedback after the component scenarios using the intended learner audience. Record whether users can complete the workflow, understand errors, interpret results and recover their prior work. Keep reported comments and participant counts separate from proposed usability improvements.')

    chapter('4. POST-DEPLOYMENT VALIDATION, DOCUMENTATION, AND LESSONS LEARNED')
    heading('4.1 Post-Deployment Validation')
    p('Post-deployment validation checks the integrated learning workflow after the selected release is installed. The procedure covers infrastructure, application dependencies, interface behavior and persistence. Validation should use representative learning material and controlled test state rather than modifying real learner records for convenience.')
    for kind,text in original_blocks(sections[5]): add(kind,text)
    heading('4.2 Validation Activities')
    add('table',[['Validation level','Activities and evidence required'],['Infrastructure','Inspect process/container status, HTTPS endpoint reachability, persistent mounts and startup logs.'],['Application','Verify dependency configuration, model response handling, error behavior and the component-specific scenarios.'],['User interface','Validate the hosted production build, uploads/actions, result display and learner-visible failure behavior.'],['Data and recovery','Restart services, confirm state retention, inspect access boundaries and verify compatible restoration.']])
    heading('4.3 Supporting Operational Artefacts')
    p('Retain the source commit, runtime/package manifests, environment-variable names, deployment scripts/configuration, model identifiers, schema versions, test output and scenario evidence with the release. Store private environment values outside the published report. The editable report source and rendered PDF provide the documentation layer; application artefacts remain in the component directory.')
    p('The following source-based limitations and supporting references remain relevant to release sign-off:')
    for kind,text in original_blocks(sections[7]): add(kind,text)
    heading('4.4 Key Lessons Learned')
    p('The following lessons are derived from implementation and deployment review. They describe engineering implications of the available source, rather than unrecorded user trials or production performance claims.')
    for lesson in c['lessons']: add('bullet',lesson)
    add('bullet','A report should distinguish the installed architecture, planned checks and measured results so that later releases remain auditable.')
    heading('4.5 Conclusion of Post-Deployment Assessment')
    p('The deployment review establishes a component-specific architecture, reproducible installation sequence, verification scenarios, monitoring plan and recovery requirements for '+c['title'].lower()+'. The identified pending items must be resolved and the acceptance evidence recorded before certifying a successful live deployment. The supporting documentation provides a reproducible operational basis for component evaluation and future releases.')
    return blocks


def flowables(blocks):
    result=[]
    for kind,text in blocks:
        if kind=='break': result.append(PageBreak())
        elif kind=='table': result.extend([grid(text),Spacer(1,12)])
        elif kind=='code':
            result.extend([para(line,'code') for line in text.splitlines()]);result.append(Spacer(1,10))
        elif kind=='bullet':
            bullet_style=ParagraphStyle('bullet',parent=styles['body'],leftIndent=18,firstLineIndent=0,bulletIndent=2,spaceAfter=6)
            result.append(Paragraph(markup(text),bullet_style,bulletText='\u2022'))
        else: result.append(para(text,kind if kind in styles else 'body'))
    return result


def cover(c):
    story=[para('Research Project<br/>(Comprehensive Design and Analysis Project)','center')]
    # Paragraph markup remains explicit only for this fixed cover line.
    story[0]=Paragraph('Research Project<br/>(Comprehensive Design and Analysis Project)',styles['center'])
    story.extend([Spacer(1,6),para('IT4010','center'),Spacer(1,18),Image(str(logo),width=126,height=126),Spacer(1,17),para('BIOLEARNX: A MULTIMODAL, MULTI-AGENT FRAMEWORK FOR PERSONALIZED BIOLOGY LEARNING','cover_title'),para(c['title'],'cover_title'),para('Deployment Report','center'),Spacer(1,22),para('Group Details','h3'),para('Group No: R26-SE-041','body'),grid([['Student ID','Student Name'],[c['sid'],c['member']]]),Spacer(1,12),para('Individual Component Deployment Report','note'),para('Prepared: 14 October 2026','note'),PageBreak()])
    return story


summary=[]
for key,c in CONFIG.items():
    target=OUT/(key+'-deployment-report.pdf')
    blocks=build_content(key,c)
    (SOURCES/(key+'-report-content.json')).write_text(json.dumps({'project':'R26-SE-041','member':c,'blocks':blocks},indent=2),encoding='utf-8')
    toc=TableOfContents()
    toc.levelStyles=[ParagraphStyle('toc0',fontName='TNR',fontSize=11,leading=15,leftIndent=0,firstLineIndent=0,spaceBefore=5),ParagraphStyle('toc1',fontName='TNR',fontSize=10.5,leading=14,leftIndent=12,firstLineIndent=0,spaceBefore=2),ParagraphStyle('toc2',fontName='TNR',fontSize=10,leading=13,leftIndent=24,firstLineIndent=0,spaceBefore=1)]
    toc.dotsMinLevel=0
    story=cover(c)+[Paragraph('TABLE OF CONTENTS',ParagraphStyle('toc_title',fontName='TNR-Bold',fontSize=14,leading=21,alignment=TA_CENTER,spaceAfter=14)),toc,NextPageTemplate('body'),PageBreak()]+flowables(blocks)
    doc=Report(str(target),title='BioLearnX - '+c['title']+' - Deployment Report',author=c['member'])
    doc.multiBuild(story)
    pdf=pymupdf.open(target)
    text=''.join(p.get_text() for p in pdf)
    for heading in ['1. DEPLOYMENT OVERVIEW','2. DEPLOYMENT PROCESS','3. ISSUES, RESOLUTION, AND MONITORING','TABLE OF CONTENTS',c['sid']]:
        if heading not in text: raise RuntimeError('Missing content: '+heading)
    thumbnails=[]
    for index,page in enumerate(pdf):
        for b in page.get_text('blocks'):
            if b[0]<23 or b[2]>A4[0]-23 or b[1]<23 or b[3]>A4[1]-23:
                raise RuntimeError(f'Out-of-bounds block in {target.name}, page {index+1}')
        path=QA/f'{key}-page-{index+1:02}.png'
        page.get_pixmap(matrix=pymupdf.Matrix(1.1,1.1),alpha=False).save(path)
        image=PILImage.open(path).convert('RGB');image.thumbnail((300,425));thumbnails.append(image)
    for offset in range(0,len(thumbnails),6):
        group=thumbnails[offset:offset+6]
        sheet=PILImage.new('RGB',(930,((len(group)+2)//3)*455),'#DDDDDD');draw=ImageDraw.Draw(sheet)
        for i,image in enumerate(group):
            x=(i%3)*310+5;y=(i//3)*455+20;sheet.paste(image,(x,y));draw.text((x,y-15),f'Page {offset+i+1}',fill='black')
        sheet.save(QA/f'{key}-contact-{offset//6+1}.png')
    summary.append({'file':str(target),'pages':len(pdf),'body_start':doc.body_start,'headings':doc.headings,'bytes':target.stat().st_size})
    pdf.close()
(QA/'validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps([{k:v for k,v in s.items() if k!='headings'} for s in summary],indent=2))
