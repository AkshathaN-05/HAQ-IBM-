import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, newIdempotencyKey, openProtectedFile, uploadFile } from '../api'
import { useI18n } from '../i18n'
import { ErrorNote, Field, Money, StatusBadge, Timeline, formatDate } from '../components/ui'
import { Thread } from './ClaimDetail'

const today = () => new Date().toISOString().slice(0, 10)

export default function EmployerClaim() {
  const { id } = useParams()
  const { t } = useI18n()
  const [claim, setClaim] = useState(null)
  const [error, setError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState({ kind: 'response', body: '' })
  const [offer, setOffer] = useState({ amount: '', explanation: '', expires_on: '' })
  const [pay, setPay] = useState({ amount: '', paid_on: today(), reference: '', receipt_evidence_id: '' })
  const [uploadPct, setUploadPct] = useState(null)
  const offerKey = useRef(newIdempotencyKey())
  const payKey = useRef(newIdempotencyKey())
  const fileRef = useRef(null)

  const load = useCallback(() => api(`/api/employer/claims/${id}`).then(setClaim).catch(setError), [id])
  useEffect(() => { load() }, [load])
  // Once the worker accepts an offer, fill the payment amount with the agreed amount.
  const agreed = claim?.settlements?.find((s) => s.status === 'accepted')?.amount
  useEffect(() => { if (agreed) setPay((p) => (p.amount ? p : { ...p, amount: String(agreed) })) }, [agreed])

  const post = async (path, body, headers) => {
    setBusy(true); setActionError(null)
    try { setClaim(await api(`/api/employer/claims/${id}${path}`, { method: 'POST', body, headers })); return true }
    catch (e) { setActionError(e); return false } finally { setBusy(false) }
  }
  const attach = async (file) => {
    if (!file) return
    setActionError(null); setUploadPct(0)
    try { await uploadFile(`/api/employer/claims/${id}/attachments`, file, setUploadPct); await load() }
    catch (e) { setActionError(e) } finally { setUploadPct(null); if (fileRef.current) fileRef.current.value = '' }
  }

  if (error) return <ErrorNote error={error} onRetry={load} />
  if (!claim) return <p className="muted">{t('loading')}</p>
  const closed = ['resolved', 'withdrawn'].includes(claim.status)
  const canOffer = !closed && !['settlement_accepted', 'payment_pending', 'partially_resolved'].includes(claim.status)
  const accepted = claim.settlements.find((s) => s.status === 'accepted')
  const waiting = claim.settlements.some((s) => s.status === 'offered')

  return (
    <div className="stack">
      <div className="card">
        <div className="row between wrap">
          <div>
            <p className="muted small">{t('reference')}: {claim.reference} · {formatDate(claim.submitted_at)}</p>
            <h1>{t('fromWorker', { name: claim.worker.display_name })}</h1>
            {claim.worker.phone && <p className="muted small">📞 {claim.worker.phone}</p>}
          </div>
          <StatusBadge status={claim.status} />
        </div>
        {claim.amount_claimed && <p className="big-number"><Money value={claim.amount_claimed} /></p>}
        <p className="note small">{t('employerCannotEdit')}</p>
        {claim.status === 'withdrawn' && <p className="note note-warn">{t('readOnlyWithdrawn')}</p>}
        {claim.status === 'submitted' && (
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => post('/acknowledge')}>{t('acknowledge')}</button>
        )}
        <ErrorNote error={actionError} />
      </div>

      <section className="card">
        <h2>{t('complaint')}</h2>
        <pre className="letter-preview">{claim.complaint_text}</pre>
        <h3>{t('sharedProof')}</h3>
        {claim.evidence.length === 0 ? <p className="muted">{t('noSharedProof')}</p> : (
          <ul className="file-list">
            {claim.evidence.map((e) => (
              <li key={e.id} className="file-item row between">
                <span>{e.label}. {e.original_name} <span className="muted small">{e.kind}</span></span>
                <button type="button" className="btn btn-small btn-ghost" onClick={() => openProtectedFile(e.id, e.original_name).catch(setActionError)}>{t('download')}</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>{t('messages')}</h2>
        <Thread messages={claim.messages} attachments={claim.employer_attachments} viewer="employer" />
        {!closed && (
          <>
            <form className="stack-s" onSubmit={async (e) => { e.preventDefault(); if (await post('/messages', msg)) setMsg({ kind: 'response', body: '' }) }}>
              <h3>{t('respond')}</h3>
              <Field label={t('msgKind')} id="mk">
                <select id="mk" value={msg.kind} onChange={(e) => setMsg((m) => ({ ...m, kind: e.target.value }))}>
                  {['response', 'question', 'agree', 'dispute'].map((k) => <option key={k} value={k}>{t(`k_${k}`)}</option>)}
                </select>
              </Field>
              <textarea aria-label={t('writeReply')} rows={4} maxLength={4000} placeholder={t('writeReply')} value={msg.body} onChange={(e) => setMsg((m) => ({ ...m, body: e.target.value }))} />
              <div className="row end"><button className="btn btn-primary" disabled={busy || !msg.body.trim()}>{t('send')}</button></div>
            </form>
            <label className="dropzone small-drop">
              <input ref={fileRef} type="file" accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.webp,.mp3,.wav,.m4a,.ogg,.webm" onChange={(e) => attach(e.target.files[0])} />
              <span className="btn btn-ghost" aria-hidden="true">📎 {t('attachFile')}</span>
              {uploadPct !== null && <span className="muted small">{t('uploading', { pct: uploadPct })}</span>}
            </label>
          </>
        )}
      </section>

      {claim.settlements.length > 0 && (
        <section className="card">
          <h2>{t('offers')}</h2>
          <ul className="offers">
            {claim.settlements.map((s) => (
              <li key={s.id} className={`offer offer-${s.status}`}>
                <div className="row between"><strong><Money value={s.amount} /></strong><span className="badge">{t(`so_${s.status}`)}</span></div>
                {s.explanation && <p className="pre small">{s.explanation}</p>}
                {s.decision_note && <p className="small muted">“{s.decision_note}”</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {waiting && !closed && <p className="note">{t('waitingOffer')}</p>}

      {canOffer && !waiting && (
        <form className="card" onSubmit={async (e) => {
          e.preventDefault()
          if (await post('/settlements', { amount: offer.amount, explanation: offer.explanation, expires_on: offer.expires_on || null }, { 'Idempotency-Key': offerKey.current })) {
            setOffer({ amount: '', explanation: '', expires_on: '' }); offerKey.current = newIdempotencyKey()
          }
        }}>
          <h2>{t('makeOffer')}</h2>
          <div className="grid-2">
            <Field label={t('offerAmount')} id="oa"><input id="oa" inputMode="decimal" required value={offer.amount} onChange={(e) => setOffer((o) => ({ ...o, amount: e.target.value }))} /></Field>
            <Field label={t('expiresOn')} id="oe"><input id="oe" type="date" min={today()} value={offer.expires_on} onChange={(e) => setOffer((o) => ({ ...o, expires_on: e.target.value }))} /></Field>
          </div>
          <Field label={t('explanation')} id="ox"><textarea id="ox" rows={2} maxLength={2000} value={offer.explanation} onChange={(e) => setOffer((o) => ({ ...o, explanation: e.target.value }))} /></Field>
          <button className="btn btn-primary" disabled={busy}>{t('sendOffer')}</button>
        </form>
      )}

      {claim.payments.length > 0 && (
        <section className="card">
          <h2>{t('payments')}</h2>
          <ul className="offers">
            {claim.payments.map((p) => (
              <li key={p.id} className="offer">
                <div className="row between"><strong><Money value={p.amount} /></strong><span className="muted small">{t('paidOn', { date: formatDate(p.paid_on) })}</span></div>
                <p className="small">{t(`wc_${p.worker_confirmation}`)}{p.worker_note ? ` — “${p.worker_note}”` : ''}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!closed && !waiting && (
        <form className="card" onSubmit={async (e) => {
          e.preventDefault()
          const body = { ...pay, receipt_evidence_id: pay.receipt_evidence_id || null, reference: pay.reference || null, settlement_id: accepted?.id || null }
          if (await post('/payments', body, { 'Idempotency-Key': payKey.current })) {
            setPay({ amount: '', paid_on: today(), reference: '', receipt_evidence_id: '' }); payKey.current = newIdempotencyKey()
          }
        }}>
          <h2>{t('recordPayment')}</h2>
          <p className="muted small">{t('paymentNote')}</p>
          <div className="grid-2">
            <Field label={t('paymentAmount')} id="pa"><input id="pa" inputMode="decimal" required value={pay.amount} onChange={(e) => setPay((p) => ({ ...p, amount: e.target.value }))} /></Field>
            <Field label={t('paymentDate')} id="pd"><input id="pd" type="date" required max={today()} value={pay.paid_on} onChange={(e) => setPay((p) => ({ ...p, paid_on: e.target.value }))} /></Field>
            <Field label={t('paymentRef')} id="pr"><input id="pr" maxLength={100} value={pay.reference} onChange={(e) => setPay((p) => ({ ...p, reference: e.target.value }))} /></Field>
            <Field label={t('receipt')} id="prc">
              <select id="prc" value={pay.receipt_evidence_id} onChange={(e) => setPay((p) => ({ ...p, receipt_evidence_id: e.target.value }))}>
                <option value="">{t('noReceipt')}</option>
                {claim.employer_attachments.map((a) => <option key={a.id} value={a.id}>{a.original_name}</option>)}
              </select>
            </Field>
          </div>
          <button className="btn btn-primary" disabled={busy}>{t('saveRecordPayment')}</button>
        </form>
      )}

      <section className="card">
        <h2>{t('timeline')}</h2>
        <Timeline events={claim.timeline} />
      </section>
    </div>
  )
}
