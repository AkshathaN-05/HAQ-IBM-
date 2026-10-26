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

const PLAN_STATUSES = ['settlement_offered', 'settlement_accepted', 'payment_pending']

export function StatusBadge({ status, issue }) {
  const { t } = useI18n()
  // For problems that are not about money, offer/payment steps are an action plan instead.
  const key = issue && issue !== 'wages' && PLAN_STATUSES.includes(status) ? `stp_${status}` : `st_${status}`
  return <span className={`badge badge-${status}`}>{t(key)}</span>
}

// The complaint letter shown as a clean document: title, bold labels and a quiet footer note.
export function LetterView({ text }) {
  if (!text) return <div className="letter-doc muted">—</div>
  const lines = text.split('\n')
  const last = lines.length - 1 - [...lines].reverse().findIndex((l) => l.trim())
  return (
    <article className="letter-doc">
      {lines.map((line, i) => {
        if (i === 0) return <h3 key={i} className="letter-title">{line}</h3>
        if (!line.trim()) return <div key={i} className="letter-gap" />
        if (i === last && line.length > 80) return <p key={i} className="letter-foot">{line}</p>
        if (/^\s{2,}\S/.test(line)) return <p key={i} className="letter-item">{line.trim()}</p>
        const m = line.match(/^([^:]{1,48}):\s?(.*)$/)
        if (m && !m[2]) return <p key={i} className="letter-section">{m[1]}</p>
        if (m) return <p key={i} className="letter-row"><span className="letter-label">{m[1]}</span><span>{m[2]}</span></p>
        return <p key={i} className="letter-text">{line}</p>
      })}
    </article>
  )
}

// A text box with voice typing. The speaking language follows the app language unless the person picks another.
export function VoiceTextarea({ id, value, onChange, rows = 3, placeholder, maxLength = 4000, label }) {
  const { t, lang } = useI18n()
  const [speechLang, setSpeechLang] = useState(lang)
  const [picked, setPicked] = useState(false)
  useEffect(() => { if (!picked) setSpeechLang(lang) }, [lang, picked])
  const valueRef = useRef(value)
  valueRef.current = value
  const speech = useSpeech(speechLang, (chunk) => onChange((valueRef.current ? valueRef.current.trimEnd() + ' ' : '') + chunk))
  return (
    <div className="voice-box">
      {label && <label htmlFor={id} className="voice-label">{label}</label>}
      <textarea id={id} rows={rows} maxLength={maxLength} placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} />
      <div className="voice-tools">
        {speech.supported ? (
          <>
            <select className="voice-lang" aria-label={t('voiceLang')} value={speechLang} onChange={(e) => { setSpeechLang(e.target.value); setPicked(true) }}>
              {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
            <button type="button" className={speech.listening ? 'btn btn-mic btn-small on' : 'btn btn-mic btn-small'} aria-pressed={speech.listening}
              onClick={speech.listening ? speech.stop : speech.start}>
              <MicIcon /> {speech.listening ? t('stopSpeaking') : t('speak')}
            </button>
          </>
        ) : <span className="muted small">{t('speechUnsupported')}</span>}
      </div>
      {speech.listening && <p className="note note-live" role="status">{t('listening')}</p>}
    </div>
  )
}

function MicIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Zm-7 9a7 7 0 0 0 14 0M12 19v3" />
    </svg>
  )
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
  // If the language changes while listening, stop; the next press records in the new language.
  useEffect(() => { recRef.current?.abort?.(); setListening(false) }, [lang])

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
