import { useState } from 'react'
import { useI18n } from '../i18n'
import { Field, VoiceTextarea, formatDate } from './ui'
import Icon from './Icon'

// What an employer can commit to, for each kind of problem that is not about money.
export const PLAN_ACTIONS = {
  safety: ['ppe', 'first_aid', 'fix_hazard', 'training', 'injury_care'],
  harassment: ['inquiry', 'separate', 'warning', 'no_retaliation', 'safe_space'],
  discrimination: ['equal_pay', 'fair_shifts', 'review', 'apology'],
  threats: ['stop', 'protect', 'police', 'separate'],
  coworkers: ['meeting', 'separate', 'rules', 'warning'],
  other: ['meeting', 'fix'],
}

const today = () => new Date().toISOString().slice(0, 10)

export function GuidanceBox({ issue }) {
  const { t } = useI18n()
  return (
    <section className="guidance">
      <p className="guidance-title"><Icon name="help" size={18} /> {t('guidanceTitle')}</p>
      <p>{t(`guide_${issue}`)}</p>
    </section>
  )
}

export function ActionPlanForm({ issue, busy, onSubmit }) {
  const { t } = useI18n()
  const options = PLAN_ACTIONS[issue] || PLAN_ACTIONS.other
  const [chosen, setChosen] = useState(() => new Set())
  const [f, setF] = useState({ custom_action: '', contact_name: '', contact_phone: '', contact_email: '', due_on: '', note: '' })
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const toggle = (k) => setChosen((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n })
  const ready = chosen.size > 0 || f.custom_action.trim()
  return (
    <form className="card" onSubmit={async (e) => {
      e.preventDefault()
      const body = { actions: [...chosen], note: f.note }
      for (const k of ['custom_action', 'contact_name', 'contact_phone', 'contact_email', 'due_on']) body[k] = f[k].trim() || null
      if (await onSubmit(body)) { setChosen(new Set()); setF({ custom_action: '', contact_name: '', contact_phone: '', contact_email: '', due_on: '', note: '' }) }
    }}>
      <h2>{t('planTitle')}</h2>
      <p className="muted small">{t('planHelp')}</p>
      <GuidanceBox issue={issue} />
      <fieldset className="plan-actions">
        <legend>{t('planChoose')}</legend>
        {options.map((k) => (
          <label key={k} className={chosen.has(k) ? 'check-row plan-option on' : 'check-row plan-option'}>
            <input type="checkbox" checked={chosen.has(k)} onChange={() => toggle(k)} />
            <span>{t(`act_${k}`)}</span>
          </label>
        ))}
      </fieldset>
      <Field label={t('planCustom')} id="pc"><input id="pc" maxLength={500} value={f.custom_action} onChange={set('custom_action')} /></Field>
      <h3>{t('planContact')}</h3>
      <p className="hint">{t('planContactHelp')}</p>
      <div className="grid-2">
        <Field label={t('planContactName')} id="pn"><input id="pn" maxLength={120} value={f.contact_name} onChange={set('contact_name')} /></Field>
        <Field label={t('planContactPhone')} id="pp"><input id="pp" inputMode="tel" maxLength={20} value={f.contact_phone} onChange={set('contact_phone')} /></Field>
        <Field label={t('planContactEmail')} id="pe"><input id="pe" type="email" value={f.contact_email} onChange={set('contact_email')} /></Field>
        <Field label={t('planDue')} id="pd"><input id="pd" type="date" min={today()} value={f.due_on} onChange={set('due_on')} /></Field>
      </div>
      <VoiceTextarea id="pnote" label={t('planNote')} rows={2} maxLength={2000} value={f.note} onChange={(v) => setF((x) => ({ ...x, note: v }))} />
      <button className="btn btn-primary" disabled={busy || !ready}>{t('sendPlan')}</button>
    </form>
  )
}

export function PlanCard({ plan, role, busy, onDecide, onDone }) {
  const { t } = useI18n()
  const [doneNote, setDoneNote] = useState('')
  const items = [...plan.actions.map((k) => t(`act_${k}`)), ...(plan.custom_action ? [plan.custom_action] : [])]
  return (
    <li className={`offer plan plan-${plan.status}`}>
      <div className="row between wrap">
        <strong>{t('planTitle')}</strong>
        <span className="badge">{t(`ps_${plan.status}`)}</span>
      </div>
      <ul className="plan-list">
        {items.map((x, i) => <li key={i}><Icon name="check" size={16} /> {x}</li>)}
      </ul>
      {(plan.contact_name || plan.contact_phone || plan.contact_email) && (
        <p className="plan-contact small">
          <span className="muted">{t('planHandledBy')}:</span> <strong>{plan.contact_name}</strong>
          {plan.contact_phone && <> · <a href={`tel:${plan.contact_phone.replace(/\s/g, '')}`}>{plan.contact_phone}</a></>}
          {plan.contact_email && <> · <a href={`mailto:${plan.contact_email}`}>{plan.contact_email}</a></>}
        </p>
      )}
      {plan.due_on && <p className="small muted">{t('planDueBy', { date: formatDate(plan.due_on) })}</p>}
      {plan.note && <p className="pre small">{plan.note}</p>}
      {plan.done_note && <p className="pre small"><span className="muted">{t('doneNoteShown')}:</span> {plan.done_note}</p>}

      {role === 'worker' && plan.status === 'proposed' && (
        <>
          <p className="muted small">{t('planAgreeNote')}</p>
          <div className="row gap">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onDecide(plan.id, 'accept')}>{t('planAgree')}</button>
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => onDecide(plan.id, 'reject')}>{t('planReject')}</button>
          </div>
        </>
      )}
      {role === 'worker' && plan.status === 'done' && plan.worker_confirmation === 'pending' && (
        <>
          <p className="small"><strong>{t('actionsDoneQ')}</strong></p>
          <div className="row gap">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onDecide(plan.id, 'confirm')}>{t('actionsYes')}</button>
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => onDecide(plan.id, 'dispute')}>{t('actionsNo')}</button>
          </div>
        </>
      )}
      {plan.status === 'done' && plan.worker_confirmation !== 'pending' && (
        <p className="small">{t(`wcp_${plan.worker_confirmation}`)}</p>
      )}

      {role === 'employer' && plan.status === 'proposed' && <p className="note small">{t('planWaiting')}</p>}
      {role === 'employer' && plan.status === 'done' && plan.worker_confirmation === 'pending' && <p className="note small">{t('doneWaiting')}</p>}
      {role === 'employer' && plan.status === 'accepted' && (
        <div className="stack-s">
          <VoiceTextarea id={`dn-${plan.id}`} label={t('doneNote')} rows={2} maxLength={2000} value={doneNote} onChange={setDoneNote} />
          <div><button type="button" className="btn btn-primary" disabled={busy} onClick={() => onDone(plan.id, doneNote)}>{t('markDone')}</button></div>
        </div>
      )}
    </li>
  )
}
