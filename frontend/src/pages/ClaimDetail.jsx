import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, openExport, openProtectedFile } from '../api'
import { useI18n } from '../i18n'
import { Confirm, ErrorNote, Money, StatusBadge, Timeline, formatDate } from '../components/ui'
import { ChecksList } from './NewClaim'
import { ProofList } from '../components/Proof'
import Icon from '../components/Icon'

export function Thread({ messages, attachments, viewer }) {
  const { t } = useI18n()
  const items = [
    ...messages.map((m) => ({ ...m, _type: 'msg' })),
    ...attachments.map((a) => ({ ...a, _type: 'file', author_role: 'employer' })),
  ].sort((a, b) => a.created_at.localeCompare(b.created_at))
  if (!items.length) return <p className="muted">{t('noMessages')}</p>
  return (
    <ul className="thread">
      {items.map((m) => (
        <li key={m.id} className={m.author_role === viewer ? 'bubble mine' : 'bubble'}>
          <div className="muted small">{t(`by_${m.author_role}`)} · {m._type === 'msg' && m.kind !== 'reply' ? `${t(`k_${m.kind}`)} · ` : ''}{formatDate(m.created_at)}</div>
          {m._type === 'msg' ? <p className="pre">{m.body}</p> : (
            <button type="button" className="link-btn" onClick={() => openProtectedFile(m.id, m.original_name)}><Icon name="clip" size={16} /> {m.original_name}</button>
          )}
        </li>
      ))}
    </ul>
  )
}

export function Tabs({ tab, setTab }) {
  const { t } = useI18n()
  return (
    <div className="segmented tabs" role="tablist">
      {['claim', 'history'].map((k) => (
        <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>
          {k === 'claim' ? t('tabClaim') : t('tabHistory')}
        </button>
      ))}
    </div>
  )
}

export default function ClaimDetail() {
  const { id } = useParams()
  const { t } = useI18n()
  const loc = useLocation()
  const [claim, setClaim] = useState(null)
  const [error, setError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [reply, setReply] = useState('')
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('claim')

  const load = useCallback(() => api(`/api/claims/${id}`).then(setClaim).catch(setError), [id])
  useEffect(() => { load() }, [load])

  const act = async (path, body = {}) => {
    setBusy(true); setActionError(null)
    try { setClaim(await api(`/api/claims/${id}${path}`, { method: 'POST', body })); return true } catch (e) { setActionError(e); return false } finally { setBusy(false) }
  }

  if (error) return <ErrorNote error={error} onRetry={load} />
  if (!claim) return <p className="muted">{t('loading')}</p>
  const open = !['draft', 'resolved', 'withdrawn'].includes(claim.status)

  const facts = [
    [t('problemLabel'), t(`issue_${claim.issue_type || 'wages'}`)],
    claim.work_type && [t('workDone'), claim.work_type],
    (claim.start_date || claim.end_date) && [t('workPeriod'), `${formatDate(claim.start_date) || '?'} – ${formatDate(claim.end_date) || '?'}`],
  ].filter(Boolean)

  return (
    <div className="stack-l">
      {loc.state?.justSent && claim.status === 'submitted' && <p className="note note-ok" role="status">✓ {t('sentOk')}</p>}
      <div className="card claim-head">
        <div className="claim-head-main">
          <p className="muted small">{t('reference')}: {claim.reference}</p>
          <h1>{claim.employer_name || t('myClaims')}</h1>
          {facts.length > 0 && <div className="facts-row">{facts.map(([k, v]) => <span key={k} className="fact"><span className="muted small">{k}</span><strong>{v}</strong></span>)}</div>}
          {claim.status === 'draft' && <Link className="btn btn-primary" to={`/worker/claims/${id}/edit?step=0`}>{t('continueEditing')}</Link>}
          {claim.submitted_at && claim.employer_account && !claim.employer_account.registered && <p className="note">{t('employerNotOnHaq')}</p>}
        </div>
        <div className="claim-head-side">
          <StatusBadge status={claim.status} />
          {claim.amount_claimed && <p className="big-number"><Money value={claim.amount_claimed} /></p>}
          <div className="row gap-s end">
            <button type="button" className="btn btn-ghost btn-small" onClick={() => openExport(id).catch(setActionError)}><Icon name="print" size={18} /> {t('exportRecord')}</button>
            {(open || claim.status === 'draft') && <Confirm className="btn btn-ghost btn-small" text={t('withdrawConfirm')} onConfirm={() => act('/withdraw')}>{t('withdraw')}</Confirm>}
            {open && <Confirm className="btn btn-ghost btn-small" text={t('closeConfirm')} onConfirm={() => act('/close')}>{t('closeResolved')}</Confirm>}
          </div>
        </div>
        <ErrorNote error={actionError} />
      </div>

      <Tabs tab={tab} setTab={setTab} />
      {tab === 'history' && (
        <section className="card">
          <h2>{t('timeline')}</h2>
          <Timeline events={claim.timeline} />
        </section>
      )}
      {tab === 'claim' && open && <Link to="/guide" className="guide-link"><Icon name="route" size={18} /> {t('guideLink')}</Link>}
      {tab === 'claim' && <div className="detail-grid">
        <div className="detail-main stack">
          <section className="card">
            <h2>{t('s5Title')}</h2>
            <pre className="letter-preview">{claim.complaint_text || '—'}</pre>
          </section>
          <section className="card">
            <h2>{t('evidence')}</h2>
            <ProofList evidence={claim.evidence} showText showShared onError={setActionError} />
            <h3>{t('checksTitle')}</h3>
            <ChecksList checks={claim.checks} />
          </section>
        </div>

        <aside className="detail-side stack">
          {claim.settlements.length > 0 && (
            <section className="card">
              <h2>{t('offers')}</h2>
              <ul className="offers">
                {claim.settlements.map((s) => (
                  <li key={s.id} className={`offer offer-${s.status}`}>
                    <div className="row between">
                      <strong>{t('offerOf', { amount: Number(s.amount).toLocaleString('en-IN') })}</strong>
                      <span className="badge">{t(`so_${s.status}`)}</span>
                    </div>
                    {s.explanation && <p className="pre">{s.explanation}</p>}
                    {s.expires_on && <p className="muted small">{t('expires', { date: formatDate(s.expires_on) })}</p>}
                    {s.status === 'offered' && claim.status === 'settlement_offered' && (
                      <>
                        <p className="muted small">{t('acceptNote')}</p>
                        <div className="row gap">
                          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => act(`/settlements/${s.id}/accept`)}>{t('accept')}</button>
                          <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => act(`/settlements/${s.id}/reject`)}>{t('reject')}</button>
                        </div>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {claim.payments.length > 0 && (
            <section className="card">
              <h2>{t('payments')}</h2>
              <ul className="offers">
                {claim.payments.map((p) => (
                  <li key={p.id} className="offer">
                    <div className="row between"><strong><Money value={p.amount} /></strong>
                      <span className="muted small">{t('paidOn', { date: formatDate(p.paid_on) })}{p.reference ? ` · ${p.reference}` : ''}</span></div>
                    {p.receipt_evidence_id && (
                      <button type="button" className="link-btn" onClick={() => openProtectedFile(p.receipt_evidence_id, 'receipt')}><Icon name="clip" size={16} /> {t('receipt')}</button>
                    )}
                    {p.worker_confirmation === 'pending' ? (
                      <div className="row gap">
                        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => act(`/payments/${p.id}/confirm`)}>{t('confirmReceived')}</button>
                        <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => act(`/payments/${p.id}/dispute`)}>{t('notReceived')}</button>
                      </div>
                    ) : <p className="small">{p.worker_confirmation === 'confirmed' ? `✓ ${t('confirmed')}` : `✗ ${t('disputed')}`}</p>}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {claim.submitted_at && (
            <section className="card">
              <h2>{t('messages')}</h2>
              <Thread messages={claim.messages} attachments={claim.employer_attachments} viewer="worker" />
              {open && (
                <form className="stack-s" onSubmit={async (e) => { e.preventDefault(); if (await act('/messages', { body: reply })) setReply('') }}>
                  <label htmlFor="reply" className="sr-only">{t('reply')}</label>
                  <textarea id="reply" rows={3} maxLength={4000} placeholder={t('writeReply')} value={reply} onChange={(e) => setReply(e.target.value)} />
                  <div className="row end"><button className="btn btn-primary" disabled={busy || !reply.trim()}>{t('send')}</button></div>
                </form>
              )}
            </section>
          )}
        </aside>
      </div>}
    </div>
  )
}
