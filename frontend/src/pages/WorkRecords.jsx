import { useEffect, useState } from 'react'
import { api } from '../api'
import { useI18n } from '../i18n'
import { ErrorNote, Field, formatDate } from '../components/ui'
import { CalcResult, PAY_TYPES } from './WageCalculator'

const EMPTY = { employer_name: '', work_type: '', pay_type: 'daily', rate: '', units: '', payments_received: '0', start_date: '', end_date: '', notes: '' }

function RecordForm({ initial, onSaved, onCancel }) {
  const { t } = useI18n()
  const [f, setF] = useState(initial || EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    const body = { ...f, start_date: f.start_date || null, end_date: f.end_date || null, notes: f.notes || null }
    delete body.id; delete body.calculation; delete body.created_at; delete body.updated_at
    try {
      const r = initial?.id ? await api(`/api/worker/engagements/${initial.id}`, { method: 'PUT', body }) : await api('/api/worker/engagements', { method: 'POST', body })
      onSaved(r)
    } catch (err) { setError(err) } finally { setBusy(false) }
  }
  return (
    <form className="card" onSubmit={submit}>
      <div className="grid-2">
        <Field label={t('employerNameShort')} id="r-en"><input id="r-en" required maxLength={150} value={f.employer_name} onChange={set('employer_name')} /></Field>
        <Field label={t('workType')} id="r-wt"><input id="r-wt" required maxLength={150} value={f.work_type} onChange={set('work_type')} /></Field>
        <Field label={t('payType')} id="r-pt"><select id="r-pt" value={f.pay_type} onChange={set('pay_type')}>{PAY_TYPES.map((p) => <option key={p} value={p}>{t(`pt_${p}`)}</option>)}</select></Field>
        <Field label={t('rate')} id="r-rate"><input id="r-rate" inputMode="decimal" required value={f.rate} onChange={set('rate')} /></Field>
        <Field label={t(`units_${f.pay_type}`)} id="r-units"><input id="r-units" inputMode="decimal" required value={f.units} onChange={set('units')} /></Field>
        <Field label={t('paymentsReceived')} id="r-paid"><input id="r-paid" inputMode="decimal" value={f.payments_received} onChange={set('payments_received')} /></Field>
        <Field label={t('startDate')} id="r-sd"><input id="r-sd" type="date" value={f.start_date || ''} onChange={set('start_date')} /></Field>
        <Field label={t('endDate')} id="r-ed"><input id="r-ed" type="date" value={f.end_date || ''} onChange={set('end_date')} /></Field>
      </div>
      <Field label={t('notes')} id="r-n"><textarea id="r-n" rows={2} maxLength={2000} value={f.notes || ''} onChange={set('notes')} /></Field>
      <ErrorNote error={error} />
      <div className="row end gap">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>{t('cancel')}</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? t('saving') : t('saveRecord')}</button>
      </div>
    </form>
  )
}

export default function WorkRecords() {
  const { t } = useI18n()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(null) // null | 'new' | record
  const load = () => api('/api/worker/engagements').then(setData).catch(setError)
  useEffect(() => { load() }, [])
  return (
    <div className="stack">
      <div className="row between">
        <h1>{t('myWorkRecords')}</h1>
        {!editing && <button type="button" className="btn btn-primary" onClick={() => setEditing('new')}>＋ {t('addRecord')}</button>}
      </div>
      {editing && <RecordForm initial={editing === 'new' ? null : editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
      <ErrorNote error={error} onRetry={load} />
      {data && data.items.length === 0 && !editing && <p className="empty">{t('noRecords')}</p>}
      {data?.items.map((r) => (
        <article key={r.id} className="card">
          <div className="row between">
            <div>
              <h2>{r.employer_name}</h2>
              <p className="muted">{r.work_type} · {t(`pt_${r.pay_type}`)}{r.start_date ? ` · ${formatDate(r.start_date)} – ${formatDate(r.end_date)}` : ''}</p>
            </div>
            <button type="button" className="btn btn-small btn-ghost" onClick={() => setEditing({ ...r, rate: String(Number(r.rate)), payments_received: String(Number(r.payments_received)) })}>✎</button>
          </div>
          <CalcResult r={r.calculation} />
        </article>
      ))}
    </div>
  )
}
