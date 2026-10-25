const fs = require('fs')
const path = require('path')
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, LevelFormat, ImageRun, Footer, PageNumber, BorderStyle, PageBreak,
} = require('docx')

// Usage: node docs/build_report.js <output.docx>   (needs: npm install docx)
const SCR = path.join(__dirname, 'screenshots')
const OUT = process.argv[2]
const GREEN = '2F6B45', CREAM = 'F7F1E3', AMBER = 'FBEFD2'
const W = 9638

const p = (text, opts = {}) => new Paragraph({ spacing: { after: 120 }, ...opts, children: runs(text) })
function runs(text) {
  // **bold** segments and `code` segments
  const out = []
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g
  let last = 0, m
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun(text.slice(last, m.index)))
    const s = m[0]
    if (s.startsWith('**')) out.push(new TextRun({ text: s.slice(2, -2), bold: true }))
    else out.push(new TextRun({ text: s.slice(1, -1), font: 'Consolas', size: 19, color: '1F4A30' }))
    last = m.index + s.length
  }
  if (last < text.length) out.push(new TextRun(text.slice(last)))
  return out
}
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] })
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] })
const bullet = (t) => new Paragraph({ numbering: { reference: 'bul', level: 0 }, spacing: { after: 60 }, children: runs(t) })

function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0)
  const scale = W / total
  const ws = widths.map((x) => Math.round(x * scale))
  ws[ws.length - 1] += W - ws.reduce((a, b) => a + b, 0)
  const border = { style: BorderStyle.SINGLE, size: 4, color: 'D8CDB0' }
  const borders = { top: border, bottom: border, left: border, right: border }
  const cell = (t, i, head) => new TableCell({
    width: { size: ws[i], type: WidthType.DXA }, borders,
    shading: head ? { type: ShadingType.CLEAR, fill: GREEN, color: 'auto' } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: String(t).split('\n').map((line) => new Paragraph({ children: head ? [new TextRun({ text: line, bold: true, color: 'FFFFFF', size: 19 })] : runs(line).map((r) => r) })),
  })
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: ws,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((c, i) => cell(c, i, false)) }))],
  })
}
const gap = () => new Paragraph({ spacing: { after: 80 }, children: [] })

function callout(lines, fill = AMBER) {
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: [W],
    rows: [new TableRow({ children: [new TableCell({
      width: { size: W, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill, color: 'auto' },
      margins: { top: 120, bottom: 120, left: 160, right: 160 },
      borders: { top: { style: BorderStyle.SINGLE, size: 6, color: 'E7C77A' }, bottom: { style: BorderStyle.SINGLE, size: 6, color: 'E7C77A' }, left: { style: BorderStyle.SINGLE, size: 24, color: 'C77D1A' }, right: { style: BorderStyle.NIL } },
      children: lines.map((l) => new Paragraph({ spacing: { after: 80 }, children: runs(l) })),
    })] })],
  })
}

function writeBox(label, n = 6) {
  const lines = [new Paragraph({ children: [new TextRun({ text: label, italics: true, color: '6B6B6B' })] })]
  for (let i = 0; i < n; i++) lines.push(new Paragraph({ border: { bottom: { style: BorderStyle.DOTTED, size: 6, color: 'BBBBBB', space: 8 } }, spacing: { after: 220 }, children: [] }))
  return lines
}

const img = (file, w, h, caption) => [
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: 'png', data: fs.readFileSync(file), transformation: { width: w, height: h } })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: caption, italics: true, size: 18, color: '5D6A5F' })] }),
]

const shots = ['07-letter', '04-evidence', '11-employer-claim'].map((n) => path.join(SCR, `report-${n}.jpg`))
const imageRow = new Table({
  width: { size: W, type: WidthType.DXA }, columnWidths: [3212, 3213, 3213],
  rows: [new TableRow({ children: shots.map((f, i) => new TableCell({
    width: { size: [3212, 3213, 3213][i], type: WidthType.DXA },
    borders: { top: { style: BorderStyle.NIL }, bottom: { style: BorderStyle.NIL }, left: { style: BorderStyle.NIL }, right: { style: BorderStyle.NIL } },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: 'jpg', data: fs.readFileSync(f), transformation: { width: 190, height: 400 } })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: ['Letter step: "no AI was used" label', 'Evidence step: extraction status', 'Employer view: only the shared file'][i], italics: true, size: 16, color: '5D6A5F' })] })],
  })) })],
})

const children = [
  // Cover
  new Paragraph({ spacing: { before: 1800, after: 200 }, children: [new TextRun({ text: 'HAQ', bold: true, size: 72, color: GREEN, font: 'Georgia' })] }),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: 'IBM Technology Contribution Report', size: 40, color: '1F4A30', font: 'Georgia' })] }),
  new Paragraph({ spacing: { after: 600 }, children: [new TextRun({ text: 'A wage-dispute documentation and resolution platform for informal workers', size: 24, color: '5D6A5F' })] }),
  table(['Item', 'Detail'], [
    ['Report date', '25 October 2026'],
    ['Project location', '`Documents\\HAQ` on the student\'s laptop'],
    ['Prepared from', 'The actual source code, configuration and test results in the HAQ repository'],
    ['Student name', '______________________________'],
    ['Programme / course', '______________________________'],
  ], [2400, 7238]),
  gap(),
  callout([
    '**How to read this report.** It separates three things clearly: (1) what is implemented in the code, (2) what was actually tested and how, and (3) what is planned. Nothing is described as working live unless it was run and observed.',
    '**Authorship.** The HAQ code and this report were produced with the help of Claude, an AI assistant by Anthropic. IBM Bob was **not** used to build the code. Section 14 is where the student records any real work done with IBM Bob afterwards, and Section 15 is for the student\'s own contribution and reflections.',
  ]),
  new Paragraph({ children: [new PageBreak()] }),

  h1('1. Project title and problem statement'),
  p('**HAQ** (हक़ / ಹಕ್ಕು — "what is rightfully yours") is a web platform that helps informal workers document unpaid-wage and other workplace disputes and resolve them with their employer.'),
  p('Domestic workers, construction labourers, drivers and other informal workers in India are often paid late, short or not at all. Their proof is scattered across WhatsApp screenshots, voice notes, UPI receipts and handwritten attendance, and formal complaint routes assume literacy, legal vocabulary and long forms. Employers, in turn, rarely receive a clear, organised claim they can answer.'),

  h1('2. Objectives and intended users'),
  table(['User', 'What HAQ lets them do'], [
    ['Worker', 'Explain the problem by typing or speaking in English, Hindi or Kannada; attach proof in any common format; review a clear complaint letter; choose exactly what to share; send it only after explicit confirmation; follow replies, accept or reject offers, and confirm or dispute payments.'],
    ['Employer', 'See only claims addressed to their verified email and only the files shared with them; acknowledge, reply, ask questions, attach files, offer a settlement and record a payment — without being able to edit the worker\'s claim.'],
  ], [1800, 7838]),
  gap(),
  p('Design objectives: never send anything without the worker\'s approval; never let AI do money arithmetic; never let AI invent facts; never claim an upload, email, submission or payment succeeded unless the server confirmed it; never label anyone a fraud.'),

  h1('3. Architecture overview'),
  p('HAQ is a React + Vite single-page app talking to a Python FastAPI backend over a JSON API. In deployment the backend also serves the built frontend, so the whole app runs as one process. Data is stored in SQLite (with versioned SQL migrations) and uploaded files in a private folder with random file names. An AI provider interface lets the complaint-drafting step use IBM Granite through IBM watsonx.ai or through Ollama on the same computer, or no AI at all.'),
  table(['Layer', 'Implementation', 'Key files'], [
    ['Web app', 'React 18, React Router 7, Vite 6; EN/HI/KN; browser voice typing', '`frontend/src/`'],
    ['API', 'FastAPI + Pydantic validation; consistent JSON errors; security headers', '`backend/app/main.py`, `routes_*.py`'],
    ['Accounts', 'One identity system; scrypt passwords; JWT with revocation; role stored server-side', '`routes_auth.py`, `security.py`'],
    ['Claims', 'Server-side state machine; messages, offers, payments, timeline, notifications', '`claim_state.py`, `routes_worker.py`, `routes_employer.py`'],
    ['Evidence', 'Validation (type, signature, size), SHA-256, private storage, background text extraction', '`evidence_files.py`'],
    ['AI drafting', 'Provider interface → IBM Granite (watsonx.ai or Ollama) or template; output validation', '`ai/providers.py`, `ai/drafting.py`'],
    ['Data', 'SQLite, migration runner, delete-blocking triggers for evidence and history', '`db.py`, `migrations/001_initial.sql`'],
  ], [1700, 5000, 2938]),

  h1('4. IBM technologies considered'),
  table(['Technology', 'Considered for', 'Decision'], [
    ['IBM Granite (instruct models)', 'Writing the plain-language "What happened" paragraph of the complaint', '**Integrated** — two ways (below)'],
    ['IBM watsonx.ai', 'Hosted access to Granite with an IBM Cloud account', '**Integrated** as `AI_PROVIDER=watsonx`'],
    ['Ollama running IBM Granite', 'Free, offline Granite on the student\'s laptop (an Ollama folder exists on the laptop)', '**Integrated** as `AI_PROVIDER=ollama`'],
    ['IBM Cloud Code Engine', 'Hosting the container', '**Prepared** (Dockerfile + steps); not deployed'],
    ['IBM Cloud Object Storage', 'Private evidence storage at scale', 'Planned; local private folder used now'],
    ['IBM Db2 / Databases for PostgreSQL', 'Managed database', 'Planned; SQLite used now'],
    ['IBM Watson Speech to Text', 'Transcribing uploaded voice notes (Hindi/Kannada)', 'Planned; browser dictation used now'],
    ['IBM watsonx.governance', 'Tracking the AI model and prompts', 'Not used — no access; noted as future work'],
    ['IBM Bob', 'AI development partner in the IDE', 'Installed on the laptop; **not used to build the code** — see Section 14'],
  ], [2500, 4100, 3038]),
  gap(),
  p('Only the smallest useful set was integrated: Granite, because the complaint narrative is the one place where a language model genuinely helps. Other IBM services were not added just to increase the number of technologies listed.'),

  h1('5. IBM technologies actually used'),
  callout([
    '**Honest status (25 Oct 2026):** IBM Granite integration is **implemented in the code and unit-tested with simulated (mocked) IBM responses**. It has **not yet been run against a live Granite model**, because no watsonx.ai API key was available and Ollama on the laptop could not be reached from the build environment. Until it is switched on, HAQ uses its deterministic template and tells the user "no AI was used".',
  ]),
  gap(),
  table(['Technology', 'Implemented', 'Tested', 'Running live'], [
    ['IBM Granite via IBM watsonx.ai (`WatsonxProvider`)', 'Yes', 'Yes — mocked HTTP (call shape, IAM token caching, errors, timeouts)', 'No — needs API key + project ID'],
    ['IBM Granite via Ollama (`OllamaProvider`)', 'Yes', 'Yes — mocked HTTP (call shape, missing-model message)', 'No — needs `ollama pull` on the laptop'],
    ['IBM Cloud Code Engine (Dockerfile)', 'Yes (file)', 'No', 'No'],
    ['IBM Bob', 'n/a', 'n/a', 'Not used yet'],
  ], [3300, 1500, 3138, 1700]),

  h1('6. Role of each implemented IBM technology'),
  h2('IBM Granite (via watsonx.ai or Ollama)'),
  p('Granite\'s job is deliberately narrow: write 3–6 plain, respectful first-person sentences for the "What happened" section of the letter, in the worker\'s chosen language, using only the worker\'s own words, the fields they entered and the text extracted from their files. Granite also returns a list of statements with the evidence labels (E1, E2…) each one relies on.'),
  p('Everything else in the letter — reference number, parties, work period, amount and wage calculation, evidence index, requested outcome and the disclaimer — is assembled by ordinary code. Money is calculated with exact decimal arithmetic and never by the model.'),
  h2('IBM Cloud Code Engine'),
  p('The Dockerfile packages the built web app and the API into one non-root container on port 8080 with Tesseract OCR for English, Hindi and Kannada, ready for `ibmcloud ce application create`. It has not been built or deployed.'),

  h1('7. How the technology connects to the application'),
  table(['Step', 'What happens', 'Where'], [
    ['1', 'Worker presses "Prepare my letter" → `POST /api/claims/{id}/draft`', '`routes_worker.py: generate_draft`'],
    ['2', 'Facts are collected; evidence text is wrapped in `<file label="E1">` tags', '`ai/drafting.py: build_facts, _user_prompt`'],
    ['3a', 'watsonx: API key exchanged for an IAM token at `iam.cloud.ibm.com` (cached), then `POST {WATSONX_URL}/ml/v1/text/chat` with `model_id`, `project_id`, system + user messages, `temperature 0`', '`ai/providers.py: WatsonxProvider`'],
    ['3b', 'Ollama: `POST {OLLAMA_URL}/api/chat` with the Granite tag, JSON format, `temperature 0`', '`ai/providers.py: OllamaProvider`'],
    ['4', 'Reply validated: must be JSON; no amount, date or evidence label that is not in the worker\'s own data', '`ai/drafting.py: validate_ai_output`'],
    ['5', 'On rejection or error → template narrative + warning shown to the worker', '`ai/drafting.py: draft_complaint`'],
    ['6', 'Letter assembled, stored as a version with provider + model, shown for editing', '`assemble`, `complaint_versions` table'],
  ], [700, 5700, 3238]),
  gap(),
  p('Configuration (no secrets in the repository): `AI_PROVIDER`, `WATSONX_URL`, `WATSONX_APIKEY`, `WATSONX_PROJECT_ID`, `WATSONX_MODEL_ID`, `OLLAMA_URL`, `OLLAMA_MODEL` in `backend/.env` (git-ignored). The API key is only used on the server and never reaches the browser. `GET /api/health` reports which provider and model are active.'),

  h1('8. Features that depend on the technology'),
  bullet('**AI-written narrative** in the complaint letter (English, Hindi or Kannada), labelled in the UI as "Written with help from IBM Granite on watsonx.ai" or "IBM Granite (local)".'),
  bullet('**Statement-to-evidence links** returned by Granite (filtered to evidence labels that really exist).'),
  bullet('Everything else in HAQ — accounts, evidence, checks, wage calculator, employer portal, settlements, payments — works **without** any IBM service. If Granite is unavailable the letter is still produced from the template, and the worker is told.'),

  h1('9. Evidence from the implementation'),
  table(['Evidence', 'Location'], [
    ['Provider classes', '`backend/app/ai/providers.py` — `WatsonxProvider`, `OllamaProvider`, `LocalTemplateProvider`'],
    ['Prompt, validation, fallback', '`backend/app/ai/drafting.py` — `SYSTEM_PROMPT`, `validate_ai_output`, `draft_complaint`'],
    ['Configuration (placeholders only)', '`backend/.env.example` lines for `AI_PROVIDER`, `WATSONX_*`, `OLLAMA_*`'],
    ['Tests', '`backend/tests/test_ai_and_reliability.py` — watsonx success + token caching; invented amount rejected; invented date / evidence label rejected; 401 and timeout fallback; credentials required; Ollama call + missing model; evidence wrapped as data'],
    ['Test result', '59 backend tests passed (Python 3.13 and 3.10); 9 frontend tests; 14/14 browser journey steps; 0 known dependency vulnerabilities'],
    ['Container', '`Dockerfile`, `.dockerignore`, DEPLOYMENT_GUIDE.md §5'],
  ], [2800, 6838]),
  gap(),
  imageRow,
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: 'Screenshots from the automated browser run. They show the app running with the template, because Granite was not yet connected.', italics: true, size: 18, color: '5D6A5F' })] }),

  h1('10. Alternatives used during local development'),
  table(['Need', 'IBM option', 'Used during development', 'Why'], [
    ['Complaint narrative', 'IBM Granite', 'Deterministic template (`LocalTemplateProvider`)', 'No live Granite access in the build environment'],
    ['Database', 'Db2 / Databases for PostgreSQL', 'SQLite', 'Zero setup on a laptop'],
    ['File storage', 'Cloud Object Storage', 'Private local folder', 'Zero setup; same access rules'],
    ['Speech', 'Watson Speech to Text', 'Browser speech recognition', 'Works without an account'],
    ['Hosting', 'Code Engine', 'Local `start.bat`', 'No IBM Cloud access'],
  ], [1800, 2300, 3000, 2538]),

  h1('11. Completed work vs planned enhancements'),
  table(['Completed and tested', 'Implemented, not live-tested', 'Planned'], [
    ['Full worker and employer journeys; accounts, roles and verification; evidence intake and extraction; checks; letter template in 3 languages; settlements and payments; wage calculator; 59 + 9 automated tests; 14-step browser test', 'Granite via watsonx.ai; Granite via Ollama; SMTP email; Code Engine container', 'Live Granite run; Cloud Object Storage; managed database; Watson Speech to Text for voice notes; letter translation for employers; watsonx.governance tracking'],
  ], [3300, 3000, 3338]),

  h1('12. Benefits, limitations and lessons learned'),
  h2('Benefits'),
  bullet('Granite can turn a worker\'s rambling spoken account into a short, calm paragraph an employer can read — in Hindi or Kannada as well as English.'),
  bullet('Running Granite locally through Ollama means a pilot can work with no cloud cost and no data leaving the laptop; watsonx.ai offers the same model family when hosting is needed.'),
  bullet('The provider interface means switching between local, watsonx.ai and Ollama is one setting.'),
  h2('Limitations'),
  bullet('Granite has not been evaluated on real worker accounts; the quality of Hindi and Kannada output is unknown until tested with native speakers.'),
  bullet('The validation catches invented amounts, dates and evidence labels, but not every possible wrong statement — the worker\'s review remains essential.'),
  bullet('The default watsonx model ID must be checked against the models offered in the user\'s project and region.'),
  h2('Lessons learned'),
  bullet('Limit the model to the one job it is good at, and keep money and structure in ordinary code.'),
  bullet('Treat uploaded evidence as untrusted data that may contain instructions.'),
  bullet('Always tell the user which tool produced a piece of text, and say so plainly when AI was not used.'),

  h1('13. Future opportunities for deeper IBM integration'),
  bullet('Run Granite live (Ollama first, then watsonx.ai) and compare letters against the template with a small set of real, anonymised accounts.'),
  bullet('IBM Watson Speech to Text for uploaded voice notes in Hindi and Kannada.'),
  bullet('IBM Cloud Object Storage (private buckets, server-side encryption) for evidence; IBM Cloud Databases or Db2 for data; Code Engine for hosting.'),
  bullet('watsonx.governance to record the model, prompt version and evaluation results for each letter.'),
  bullet('Granite for translating the letter for the employer, with the same validation rules.'),

  h1('14. IBM Bob — contribution record'),
  callout([
    '**Status at hand-over:** IBM Bob is installed on the laptop but was **not used** to write, review or test any of the HAQ code described above.',
    'To complete this section truthfully, follow `BOB_GUIDE.md` (Ask-mode explanations, `/review` code review, Code-mode tests, Plan-mode designs), record each session in `BOB_CONTRIBUTION_LOG.md`, then summarise below. Delete this box when done.',
  ]),
  gap(),
  table(['Bob mode / feature', 'What Bob did (your words)', 'Kept?', 'Files / tests affected'], [
    ['Ask', '', '', ''], ['/review', '', '', ''], ['Code', '', '', ''], ['Plan', '', '', ''],
  ], [1900, 4300, 1000, 2438]),
  gap(),
  ...writeBox('How IBM Bob helped (only what actually happened):', 6),

  h1('15. My own contribution, learning and reflections'),
  p('To be written by the student after reviewing and working with the project. Describe only what you personally did — for example: choosing the problem, testing the app, running the demo, using IBM Bob, setting up Granite, fixing or adding something, presenting the project.'),
  ...writeBox('What I did personally:', 5),
  ...writeBox('What I learned:', 4),
  ...writeBox('What I would do next:', 3),

  h1('16. Conclusion'),
  p('HAQ is a complete, working and tested platform for documenting and resolving wage disputes, built so that a worker with limited digital skills can explain a problem, organise proof, understand the complaint and decide what to do next. IBM Granite is integrated in a careful, narrow role — writing the plain-language narrative — behind a validation layer that stops it from inventing money amounts, dates or evidence, with both an IBM watsonx.ai path and a free local Ollama path. That integration is implemented and unit-tested but still has to be switched on and evaluated live; the remaining IBM services (Code Engine, Cloud Object Storage, Speech to Text) are prepared or planned rather than in use.'),
]

const doc = new Document({
  creator: 'HAQ project',
  title: 'IBM Technology Contribution Report — HAQ',
  styles: {
    default: { document: { run: { font: 'Calibri', size: 21, color: '1D2A20' } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Georgia', size: 32, bold: true, color: GREEN }, paragraph: { keepNext: true, keepLines: true, spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: 'Georgia', size: 25, bold: true, color: '1F4A30' }, paragraph: { keepNext: true, keepLines: true, spacing: { before: 220, after: 100 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'HAQ — IBM Technology Contribution Report · page ', size: 16, color: '888888' }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: '888888' })] })] }) },
    children,
  }],
})
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(OUT, b); console.log('wrote', OUT) })
