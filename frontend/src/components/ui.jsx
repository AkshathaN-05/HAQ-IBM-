import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { LANGS, useI18n } from '../i18n'

export function errorText(t, err) {
  if (!err) return ''
  if (err.code === 'network_error') return t('networkError')
  return err.message || String(err)
}

export function ErrorNote({ error, onRetry }) {
  const { t } = useI18n()
  if (!error) return null
  return (
    <div className="note note-error" role="alert">
      <span>{errorText(t, error)}</span>
      {onRetry && <button type="button" className="btn btn-small btn-ghost" onClick={onRetry}>{t('retry')}</button>}
    </div>
  )
}

export function Field({ label, hint, children, id }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && <p className="hint">{hint}</p>}
    </div>
  )
}

export function StatusBadge({ status }) {
  const { t } = useI18n()
  return <span className={`badge badge-${status}`}>{t(`st_${status}`)}</span>
}

export function Money({ value }) {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return <>₹{n.toLocaleString('en-IN', { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 })}</>
}

export function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', ...(iso.length > 10 ? { hour: '2-digit', minute: '2-digit' } : {}) })
}

export function Timeline({ events }) {
  const { t } = useI18n()
  if (!events?.length) return null
  return (
    <ol className="timeline">
      {events.map((e, i) => (
        <li key={i}>
          <span className="tl-dot" aria-hidden="true" />
          <div>
            <strong>{t(`ev_${e.type}`)}</strong>
            {e.detail?.file && <span className="muted"> — {e.detail.file}</span>}
            {e.detail?.amount && <span className="muted"> — <Money value={e.detail.amount} /></span>}
            <div className="muted small">{formatDate(e.created_at)} · {t(`by_${e.actor_role}`)}</div>
          </div>
        </li>
      ))}
    </ol>
  )
}

export function LanguagePicker({ compact }) {
  const { lang, setLang, t } = useI18n()
  return (
    <label className={compact ? 'lang-picker compact' : 'lang-picker'}>
      <span className={compact ? 'sr-only' : ''}>{t('language')}</span>
      <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label={t('language')}>
        {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
      </select>
    </label>
  )
}

// Voice typing using the browser's own speech recognition (Chrome/Edge/Android).
export function useSpeech(speechLang, onText) {
  const { lang: uiLang } = useI18n()
  const lang = speechLang || uiLang
  const recRef = useRef(null)
  const [listening, setListening] = useState(false)
  const SR = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)
  const supported = Boolean(SR)
  const cbRef = useRef(onText)
  cbRef.current = onText

  useEffect(() => () => recRef.current?.abort?.(), [])

  const start = () => {
    if (!SR) return
    const rec = new SR()
    // "other" language: let the browser use the phone's own language setting
    rec.lang = LANGS.find((l) => l.code === lang)?.speech || navigator.language || 'en-IN'
    rec.continuous = true
    rec.interimResults = false
    rec.onresult = (e) => {
      let text = ''
      for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) text += e.results[i][0].transcript
      if (text) cbRef.current(text.trim())
    }
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    recRef.current = rec
    rec.start()
    setListening(true)
  }
  const stop = () => { recRef.current?.stop(); setListening(false) }
  return { supported, listening, start, stop }
}

export function VerifyEmailCard() {
  const { user, setUser } = useAuth()
  const { t } = useI18n()
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState('')
  const [devMail, setDevMail] = useState(null)

  const loadDev = async () => {
    try {
      const d = await api(`/api/dev/outbox?email=${encodeURIComponent(user.email)}`)
      setDevMail(d.items[0] || null)
    } catch { setDevMail(null) }
  }
  useEffect(() => { if (user && !user.email_verified) loadDev() }, [user]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!user || user.email_verified) return null
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const d = await api('/api/auth/verify-email', { method: 'POST', body: { code } })
      setUser(d.user)
    } catch (err) { setError(err) } finally { setBusy(false) }
  }
  const resend = async () => {
    setError(null)
    try {
      const d = await api('/api/auth/resend-verification', { method: 'POST' })
      setInfo(d.status === 'failed' ? 'Email could not be sent. Please try later.' : '✓')
      loadDev()
    } catch (err) { setError(err) }
  }
  return (
    <section className="card card-warn" aria-labelledby="verify-h">
      <h2 id="verify-h">{t('verifyTitle')}</h2>
      <p>{t('verifyText', { email: user.email })}</p>
      <form className="row" onSubmit={submit}>
        <input inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} required
          aria-label={t('verifyCode')} placeholder="123456" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} className="code-input" />
        <button className="btn btn-primary" disabled={busy || code.length !== 6}>{t('verify')}</button>
        <button type="button" className="btn btn-ghost" onClick={resend}>{t('resendCode')}</button>
      </form>
      {info && <p className="muted small">{info}</p>}
      <ErrorNote error={error} />
      {devMail && (
        <div className="dev-box">
          <p className="small"><strong>DEV</strong> — {t('devCodeNote')}</p>
          <pre>{devMail.body}</pre>
        </div>
      )}
    </section>
  )
}

export function Confirm({ text, onConfirm, children, className = 'btn btn-ghost' }) {
  return <button type="button" className={className} onClick={() => { if (window.confirm(text)) onConfirm() }}>{children}</button>
}
