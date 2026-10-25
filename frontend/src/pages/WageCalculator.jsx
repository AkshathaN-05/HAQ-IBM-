import { useState } from 'react'
import { api } from '../api'
import { useI18n } from '../i18n'
import { ErrorNote, Field, Money } from '../components/ui'

export const PAY_TYPES = ['daily', 'hourly', 'weekly', 'monthly', 'piece', 'task']

export function CalcResult({ r }) {
  const { t } = useI18n()
  if (!r) return null
  return (
    <div className="calc-result" role="status">
      <div><span>{t('expectedWages')}</span><strong><Money value={r.expected_wages} /></strong></div>
      <div><span>{t('totalPaid')}</span><strong><Money value={r.payments_received} /></strong></div>
      {Number(r.potential_outstanding) > 0 && <div className="hl"><span>{t('outstanding')}</span><strong><Money value={r.potential_outstanding} /></strong></div>}
      {Number(r.excess_payment) > 0 && <div><span>{t('excess')}</span><strong><Money value={r.excess_payment} /></strong></div>}
      <p className="muted small">{r.formula}</p>
      <p className="note small">{t('estimateNote')}</p>
    </div>
  )
}

export default function WageCalculator() {
  const { t } = useI18n()
  const [f, setF] = useState({ pay_type: 'daily', rate: '', units: '', payments_received: '0' })
  const [res, setRes] = useState(null)
  const [error, setError] = useState(null)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try { setRes(await api('/api/wage-calculation', { method: 'POST', body: f })) } catch (err) { setRes(null); setError(err) }
  }
  return (
    <div className="narrow">
      <form className="card" onSubmit={submit}>
        <h1>{t('wageCalculator')}</h1>
        <Field label={t('payType')} id="pt">
          <select id="pt" value={f.pay_type} onChange={set('pay_type')}>{PAY_TYPES.map((p) => <option key={p} value={p}>{t(`pt_${p}`)}</option>)}</select>
        </Field>
        <div className="grid-2">
          <Field label={t('rate')} id="rate"><input id="rate" inputMode="decimal" required value={f.rate} onChange={set('rate')} /></Field>
          <Field label={t(`units_${f.pay_type}`)} id="units"><input id="units" inputMode="decimal" required value={f.units} onChange={set('units')} /></Field>
        </div>
        <Field label={t('paymentsReceived')} id="paid"><input id="paid" inputMode="decimal" value={f.payments_received} onChange={set('payments_received')} /></Field>
        <ErrorNote error={error} />
        <button className="btn btn-primary btn-block">{t('calculate')}</button>
        <CalcResult r={res} />
      </form>
    </div>
  )
}
