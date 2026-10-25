import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, newIdempotencyKey, uploadFile } from '../api'
import { useAuth } from '../auth'
import { LANGS, useI18n } from '../i18n'
import { ErrorNote, Field, Money, VerifyEmailCard, errorText, formatDate, useSpeech } from '../components/ui'
import Icon from '../components/Icon'

const STEPS = 4
export const ISSUES = ['wages', 'safety', 'harassment', 'discrimination', 'threats', 'coworkers', 'other']
const fileSize = (b) => (b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(0)} KB` : `${(b / 1048576).toFixed(1)} MB`)
const localKey = (id) => `haq.localDraft.${id || 'new'}`

function readLocal(id) {
  try { return JSON.parse(localStorage.getItem(localKey(id)) || 'null') } catch { return null }
}
function writeLocal(id, data) {
  try { localStorage.setItem(localKey(id), JSON.stringify(data)) } catch { /* storage full or blocked */ }
}
function clearLocal(id) {
  try { localStorage.removeItem(localKey(id)) } catch { /* ignore */ }
}

function Progress({ step }) {
  const { t } = useI18n()
  return (
    <div className="wizard-progress" aria-label={t('step', { n: step + 1, total: STEPS })}>
      <div className="muted small">{t('step', { n: step + 1, total: STEPS })}</div>
      <div className="bar"><span style={{ width: `${((step + 1) / STEPS) * 100}%` }} /></div>
    </div>
  )
}

// ---------- Step 1: describe ----------
function StepDescribe({ claim, onSaved, initialType }) {
  const { t, lang } = useI18n()
  // The button the worker pressed decides the page; each button keeps its own saved draft on this device.
  const mode = claim ? (claim.issue_type === 'wages' ? 'wages' : 'problem') : (initialType === 'problem' ? 'problem' : 'wages')
  const draftKey = claim?.id || `new-${mode}`
  const local = readLocal(draftKey)
  // 'wages' = came from "Unpaid wages" (no list shown); 'problem' = came from "Another problem at work" (list without wages)
  const saved = claim?.issue_type || local?.issue_type
  const [issue, setIssue] = useState(mode === 'wages' ? 'wages' : (saved && saved !== 'wages' ? saved : ''))
  const choices = ISSUES.filter((k) => k !== 'wages')
  const [text, setText] = useState(local?.description ?? claim?.description ?? '')
  const [language, setLanguage] = useState(claim?.language || local?.language || lang)
  const [dirty, setDirty] = useState(Boolean(local))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const speech = useSpeech(language, (chunk) => { setText((prev) => (prev ? prev.trimEnd() + ' ' : '') + chunk); setDirty(true) })

  useEffect(() => {
    if (dirty) writeLocal(draftKey, { description: text, language, issue_type: issue })
  }, [text, language, issue, dirty, draftKey])
  useEffect(() => {
    if (!dirty) return undefined
    const h = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', h)
    return () => window.removeEventListener('beforeunload', h)
  }, [dirty])

  const save = async () => {
    setBusy(true); setError(null)
    try {
      const c = claim
        ? await api(`/api/claims/${claim.id}`, { method: 'PATCH', body: { description: text, language, issue_type: issue } })
        : await api('/api/claims', { method: 'POST', body: { description: text, language, issue_type: issue } })
      clearLocal(draftKey); clearLocal(c.id)
      setDirty(false)
      onSaved(c)
    } catch (e) { setError(e) } finally { setBusy(false) }
  }

  return (
    <section className="card">
      <h1>{t('s1Title')}</h1>
      <p className="muted">{t('s1Help')}</p>
      {mode === 'wages' ? (
        <p className="issue-chosen"><span className="tag">{t('issue_wages')}</span></p>
      ) : (
      <fieldset className="issue-picker">
        <legend>{t('issueTitle')}</legend>
        <div className="issue-grid">
          {choices.map((k) => (
            <label key={k} className={issue === k ? 'issue-option on' : 'issue-option'}>
              <input type="radio" name="issue" value={k} checked={issue === k} onChange={() => { setIssue(k); setDirty(true) }} />
              <span>{t(`issue_${k}`)}</span>
            </label>
          ))}
        </div>
      </fieldset>
      )}
      <div className="row gap">
        <label className="lang-picker">
          <span>{t('language')}</span>
          <select value={language} onChange={(e) => { setLanguage(e.target.value); setDirty(true) }}>
            {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            <option value="other">{t('otherLanguage')}</option>
          </select>
        </label>
        {speech.supported ? (
          <button type="button" className={speech.listening ? 'btn btn-mic on' : 'btn btn-mic'} onClick={speech.listening ? speech.stop : speech.start} aria-pressed={speech.listening}>
            <Icon name="mic" size={18} /> {speech.listening ? t('stopSpeaking') : t('speak')}
          </button>
        ) : <p className="muted small">{t('speechUnsupported')}</p>}
      </div>
      <p className="hint">{t('anyLanguageNote')}{language === 'other' ? ` ${t('otherLanguageNote')}` : ''}</p>
      {speech.listening && <p className="note note-live" role="status">{t('listening')}</p>}
      <label htmlFor="desc" className="sr-only">{t('s1Title')}</label>
      <textarea id="desc" rows={8} maxLength={8000} value={text} placeholder={mode === 'wages' ? t('s1Placeholder') : t('s1PlaceholderOther')}
        onChange={(e) => { setText(e.target.value); setDirty(true) }} />
      {speech.supported && <p className="hint">{t('speechNote')}</p>}
      {dirty && (
        <p className="hint row gap-s">
          <span>{t('localDraftSaved')}</span>
          <button type="button" className="link-btn" onClick={() => { clearLocal(draftKey); setText(claim?.description || ''); setDirty(false) }}>{t('deleteLocalDraft')}</button>
        </p>
      )}
      <ErrorNote error={error} onRetry={save} />
      <div className="row end">
        <button type="button" className="btn btn-primary" disabled={busy || !issue || text.trim().length < 10} onClick={save}>{busy ? t('saving') : t('next')}</button>
      </div>
    </section>
  )
}

// ---------- Step 2: evidence ----------
function EvidenceItem({ ev, claimId, onChanged }) {
  const { t } = useI18n()
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(ev.extracted_text || '')
  const [error, setError] = useState(null)
  // Files are read in the background, so refresh the box once the text arrives (unless the worker is typing in it).
  useEffect(() => { if (!editing) setText(ev.extracted_text || '') }, [ev.extracted_text, editing])
  const label = { pending: t('reading'), done: t('readDone'), unsupported: t('readUnsupported'), failed: t('readFailed') }[ev.extraction_status]
  const save = async () => {
    setError(null)
    try { onChanged(await api(`/api/claims/${claimId}/evidence/${ev.id}`, { method: 'PATCH', body: { extracted_text: text } })); setEditing(false) } catch (e) { setError(e) }
  }
  return (
    <li className="file-item">
      <div className="row between">
        <div>
          <strong>{ev.label}. {ev.original_name}</strong>
          <div className="muted small">{ev.kind} · {fileSize(ev.size_bytes)} · <span className={`ex ex-${ev.extraction_status}`}>{label}</span></div>
        </div>
        {(ev.extraction_status === 'done' || ev.extraction_status === 'failed' || ev.extraction_status === 'unsupported') && (
          <button type="button" className="btn btn-small btn-ghost" aria-expanded={editing} onClick={() => { if (!editing) setText(ev.extracted_text || ''); setEditing((e) => !e) }}>{editing ? t('hideText') : t('editText')}</button>
        )}
      </div>
      {ev.extraction_error && <p className="muted small">{ev.extraction_error}</p>}
      {ev.found_amounts?.length > 0 && <p className="small">{t('amountsFound', { list: ev.found_amounts.map((a) => `₹${Number(a).toLocaleString('en-IN')}`).join(', ') })}</p>}
      {ev.found_dates?.length > 0 && <p className="small">{t('datesFound', { list: ev.found_dates.map(formatDate).join(', ') })}</p>}
      {editing && (
        <div className="stack-s">
          <label htmlFor={`t-${ev.id}`} className="small">{t('textFromFile')}</label>
          <textarea id={`t-${ev.id}`} rows={Math.min(14, Math.max(4, text.split('\n').length + 1))} value={text} onChange={(e) => setText(e.target.value)} />
          <ErrorNote error={error} />
          <div className="row end"><button type="button" className="btn btn-small btn-primary" onClick={save}>{t('saveText')}</button></div>
        </div>
      )}
    </li>
  )
}

function StepEvidence({ claim, refresh, setClaim, next, back }) {
  const { t } = useI18n()
  const [uploads, setUploads] = useState([]) // local upload jobs
  const inputRef = useRef(null)

  const runUpload = useCallback(async (job) => {
    setUploads((u) => u.map((x) => (x.id === job.id ? { ...x, state: 'uploading', pct: 0, error: null } : x)))
    try {
      await uploadFile(`/api/claims/${claim.id}/evidence`, job.file, (pct) =>
        setUploads((u) => u.map((x) => (x.id === job.id ? { ...x, pct } : x))))
      setUploads((u) => u.filter((x) => x.id !== job.id))
      refresh()
    } catch (e) {
      setUploads((u) => u.map((x) => (x.id === job.id ? { ...x, state: 'failed', error: e } : x)))
    }
  }, [claim.id, refresh])

  const onFiles = (files) => {
    const jobs = Array.from(files).map((f) => ({ id: `${f.name}-${f.size}-${Math.random()}`, file: f, state: 'queued', pct: 0 }))
    setUploads((u) => [...u, ...jobs])
    jobs.forEach(runUpload)
    if (inputRef.current) inputRef.current.value = ''
  }

  const pending = claim.evidence.some((e) => e.extraction_status === 'pending')
  useEffect(() => {
    if (!pending) return undefined
    const id = setInterval(refresh, 2000)
    return () => clearInterval(id)
  }, [pending, refresh])

  return (
    <section className="card">
      <h1>{t('s2Title')}</h1>
      <p className="muted">{t('s2Help')}</p>
      <label className="dropzone">
        <input ref={inputRef} type="file" multiple onChange={(e) => onFiles(e.target.files)}
          accept=".jpg,.jpeg,.png,.webp,.pdf,.docx,.txt,.mp3,.wav,.m4a,.ogg,.opus,.webm,.mp4,.mov,image/*,audio/*,video/*,application/pdf" />
        <span className="btn btn-primary" aria-hidden="true">＋ {t('addFiles')}</span>
        <span className="muted small">JPG · PNG · PDF · DOCX · MP3 · WAV · M4A · MP4 · MOV</span>
      </label>
      {uploads.length > 0 && (
        <ul className="file-list">
          {uploads.map((u) => (
            <li key={u.id} className="file-item">
              <strong>{u.file.name}</strong>
              {u.state === 'uploading' && <div className="bar small-bar" aria-label={t('uploading', { pct: u.pct })}><span style={{ width: `${u.pct}%` }} /></div>}
              {u.state === 'uploading' && <span className="muted small">{t('uploading', { pct: u.pct })}</span>}
              {u.state === 'failed' && (
                <div className="note note-error row between">
                  <span>{t('uploadFailed')}: {errorText(t, u.error)}</span>
                  <span className="row gap-s">
                    <button type="button" className="btn btn-small btn-ghost" onClick={() => runUpload(u)}>{t('retry')}</button>
                    <button type="button" className="btn btn-small btn-ghost" onClick={() => setUploads((x) => x.filter((y) => y.id !== u.id))}>{t('close')}</button>
                  </span>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {claim.evidence.length === 0 && uploads.length === 0 && <p className="empty">{t('noFilesYet')}</p>}
      <ul className="file-list">
        {claim.evidence.map((ev) => <EvidenceItem key={ev.id} ev={ev} claimId={claim.id} onChanged={setClaim} />)}
      </ul>
      <div className="row between">
        <button type="button" className="btn btn-ghost" onClick={back}>{t('back')}</button>
        <button type="button" className="btn btn-primary" onClick={next} disabled={uploads.some((u) => u.state === 'uploading')}>{t('next')}</button>
      </div>
    </section>
  )
}

// ---------- Step 3: key details (only what is needed) ----------
function StepDetails({ claim, setClaim, next, back }) {
  const { t } = useI18n()
  const wages = claim.issue_type === 'wages'
  const [f, setF] = useState({
    employer_name: claim.employer_name || '', employer_email: claim.employer_email || '', work_type: claim.work_type || '',
    start_date: claim.start_date || '', end_date: claim.end_date || '', amount_claimed: claim.amount_claimed ? String(Number(claim.amount_claimed)) : '',
    requested_outcome: claim.requested_outcome || t(`outcome_${claim.issue_type || 'wages'}`),
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const amounts = useMemo(() => [...new Set(claim.evidence.flatMap((e) => e.found_amounts || []))].slice(0, 6), [claim.evidence])
  const dates = useMemo(() => [...new Set(claim.evidence.flatMap((e) => e.found_dates || []))].sort().slice(0, 6), [claim.evidence])

  const save = async () => {
    setBusy(true); setError(null)
    const body = {}
    for (const [k, v] of Object.entries(f)) body[k] = v.trim() === '' ? null : v.trim()
    if (!wages) delete body.amount_claimed
    try { setClaim(await api(`/api/claims/${claim.id}`, { method: 'PATCH', body })); next() } catch (e) { setError(e) } finally { setBusy(false) }
  }
  const fe = (name) => error?.details?.field === name || error?.details?.fields?.some((x) => x.field === name)
  const Suggest = ({ items, onPick, fmt }) => items.length > 0 && (
    <div className="suggest"><span className="muted small">{t('suggested')}</span>{items.map((v) => (
      <button key={v} type="button" className="chip" onClick={() => onPick(v)}>{fmt(v)}</button>))}</div>
  )
  return (
    <section className="card">
      <h1>{t('s3Title')}</h1>
      <p className="muted">{t('s3Help')}</p>
      <div className="grid-2">
        <Field label={t('employerName')} id="en"><input id="en" maxLength={150} value={f.employer_name} onChange={set('employer_name')} /></Field>
        <Field label={t('employerEmail')} id="ee"><input id="ee" type="email" value={f.employer_email} onChange={set('employer_email')} aria-invalid={fe('employer_email')} /></Field>
        <Field label={t('workType')} id="wt"><input id="wt" maxLength={150} value={f.work_type} onChange={set('work_type')} /></Field>
        {wages && (
          <Field label={t('amountClaimed')} id="am">
            <input id="am" inputMode="decimal" value={f.amount_claimed} onChange={set('amount_claimed')} aria-invalid={fe('amount_claimed')} />
            <Suggest items={amounts} onPick={(v) => setF((x) => ({ ...x, amount_claimed: String(Number(v)) }))} fmt={(v) => `₹${Number(v).toLocaleString('en-IN')}`} />
          </Field>
        )}
        <Field label={t('startDate')} id="sd">
          <input id="sd" type="date" value={f.start_date} onChange={set('start_date')} />
          <Suggest items={dates} onPick={(v) => setF((x) => ({ ...x, start_date: v }))} fmt={formatDate} />
        </Field>
        <Field label={t('endDate')} id="ed">
          <input id="ed" type="date" value={f.end_date} onChange={set('end_date')} />
          <Suggest items={dates} onPick={(v) => setF((x) => ({ ...x, end_date: v }))} fmt={formatDate} />
        </Field>
      </div>
      <Field label={t('outcome')} id="oc"><textarea id="oc" rows={2} maxLength={1000} value={f.requested_outcome} onChange={set('requested_outcome')} /></Field>
      <ErrorNote error={error} />
      <div className="row between">
        <button type="button" className="btn btn-ghost" onClick={back}>{t('back')}</button>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={save}>{busy ? t('saving') : t('next')}</button>
      </div>
    </section>
  )
}

// ---------- Step 4: summary & checks ----------
export function ChecksList({ checks }) {
  const { t } = useI18n()
  if (!checks?.length) return <p className="muted">{t('noChecks')}</p>
  return (
    <ul className="checks">
      {checks.map((c, i) => (
        <li key={i} className={`check check-${c.classification}`}>
          <span className="check-label">{t(`cls_${c.classification}`)}</span>
          <span>{c.message}{c.evidence?.length > 0 && <span className="muted"> ({c.evidence.map((e) => e.label).join(', ')})</span>}</span>
        </li>
      ))}
    </ul>
  )
}

// ---------- Step 4: check and send (summary, checks, letter and sharing on one page) ----------
function StepReview({ claim, setClaim, back }) {
  const { t } = useI18n()
  const { user } = useAuth()
  const nav = useNavigate()
  const [text, setText] = useState(claim.complaint_text || '')
  const [meta, setMeta] = useState(null)
  const [drafting, setDrafting] = useState(false)
  const [shared, setShared] = useState(() => new Set(claim.evidence.map((e) => e.id)))
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const key = useRef(newIdempotencyKey()) // reused on retry so a double-tap cannot send twice
  const started = useRef(false)
  const toggle = (id) => setShared((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })

  const generate = useCallback(async () => {
    setDrafting(true); setError(null)
    try {
      const d = await api(`/api/claims/${claim.id}/draft`, { method: 'POST' })
      setClaim(d.claim); setText(d.draft.text); setMeta(d.draft)
    } catch (e) { setError(e) } finally { setDrafting(false) }
  }, [claim.id, setClaim])
  // The letter is prepared automatically the first time this step opens.
  useEffect(() => { if (!started.current && !claim.complaint_text) { started.current = true; generate() } }, [claim.complaint_text, generate])

  const send = async () => {
    setBusy(true); setError(null)
    try {
      if (text !== (claim.complaint_text || '')) await api(`/api/claims/${claim.id}`, { method: 'PATCH', body: { complaint_text: text } })
      await api(`/api/claims/${claim.id}/submit`, {
        method: 'POST', headers: { 'Idempotency-Key': key.current },
        body: { confirm: true, complaint_text: text, shared_evidence_ids: [...shared] },
      })
      // Navigate only after the server confirmed the submission.
      nav(`/worker/claims/${claim.id}`, { replace: true, state: { justSent: true } })
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  const blocked = !user.email_verified ? t('needVerify') : !claim.employer_email ? t('needEmployerEmail') : null
  const m = <em className="missing">{t('missing')}</em>
  return (
    <section className="card">
      <h1>{t('reviewTitle')}</h1>
      <p className="muted">{t('reviewHelp')}</p>
      <dl className="summary">
        <dt>{t('issueTitle')}</dt><dd>{t(`issue_${claim.issue_type || 'wages'}`)}</dd>
        <dt>{t('employerNameShort')}</dt><dd>{claim.employer_name || m}{claim.employer_email && <span className="muted"> · {claim.employer_email}</span>}</dd>
        {claim.issue_type === 'wages' && <><dt>{t('amount')}</dt><dd>{claim.amount_claimed ? <Money value={claim.amount_claimed} /> : m}</dd></>}
      </dl>
      <h2>{t('checksTitle')}</h2>
      <ChecksList checks={claim.checks} />

      <div className="row between wrap">
        <h2>{t('s5Title')}</h2>
        <button type="button" className="btn btn-ghost btn-small" onClick={generate} disabled={drafting}>{drafting ? t('preparing') : t('remakeDraft')}</button>
      </div>
      {meta?.source === 'ai' && (
        <p className="note note-ai">{t('draftByAi', { provider: meta.provider === 'ibm-watsonx' ? 'IBM Granite on watsonx.ai' : 'IBM Granite (local)', model: meta.model })}</p>
      )}
      {drafting && !text && <p className="muted">{t('preparing')}</p>}
      {text && (
        <>
          <label htmlFor="complaint" className="sr-only">{t('s5Title')}</label>
          <textarea id="complaint" className="letter" rows={16} value={text} onChange={(e) => setText(e.target.value)} />
        </>
      )}

      {claim.evidence.length > 0 && (
        <fieldset className="share-list">
          <legend>{t('evidence')}</legend>
          {claim.evidence.map((e) => (
            <label key={e.id} className="check-row">
              <input type="checkbox" checked={shared.has(e.id)} onChange={() => toggle(e.id)} />
              <span>{e.label}. {e.original_name} <span className="muted small">— {t('shareFile')}</span></span>
            </label>
          ))}
        </fieldset>
      )}
      <VerifyEmailCard />
      {blocked && <p className="note note-warn">{blocked}</p>}
      <label className="check-row confirm">
        <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
        <span>{t('confirmSend', { employer: claim.employer_name || claim.employer_email || '—' })}</span>
      </label>
      <ErrorNote error={error} />
      <div className="row between">
        <button type="button" className="btn btn-ghost" onClick={back}>{t('back')}</button>
        <button type="button" className="btn btn-primary" disabled={!confirm || busy || drafting || Boolean(blocked) || text.trim().length < 20} onClick={send}>{busy ? t('sending') : t('sendClaim')}</button>
      </div>
    </section>
  )
}

export default function NewClaim() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const nav = useNavigate()
  const { t } = useI18n()
  const [claim, setClaim] = useState(null)
  const [error, setError] = useState(null)
  const step = Math.min(Math.max(Number(params.get('step') || (id ? 1 : 0)), 0), STEPS - 1)
  const go = (s) => setParams({ step: String(s) })

  const refresh = useCallback(async () => {
    if (!id) return
    try { setClaim(await api(`/api/claims/${id}`)) } catch (e) { setError(e) }
  }, [id])
  useEffect(() => { setClaim(null); refresh() }, [refresh])

  useEffect(() => {
    if (claim && claim.status !== 'draft') nav(`/worker/claims/${claim.id}`, { replace: true })
  }, [claim, nav])

  if (id && !claim) return error ? <ErrorNote error={error} onRetry={refresh} /> : <p className="muted">{t('loading')}</p>

  const common = { claim, setClaim, refresh, next: () => go(step + 1), back: () => go(step - 1) }
  return (
    <div className="stack wizard">
      <div className="row between">
        <Progress step={step} />
        {claim && <Link to="/worker" className="small">{t('saveDraftExit')}</Link>}
      </div>
      {step === 0 && <StepDescribe claim={claim} initialType={params.get('type') || undefined} onSaved={(c) => { setClaim(c); if (!id) nav(`/worker/claims/${c.id}/edit?step=1`, { replace: true }); else go(1) }} />}
      {step === 1 && claim && <StepEvidence {...common} />}
      {step === 2 && claim && <StepDetails {...common} />}
      {step === 3 && claim && <StepReview {...common} />}
    </div>
  )
}
