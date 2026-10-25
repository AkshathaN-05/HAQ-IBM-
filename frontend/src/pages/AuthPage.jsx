import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { ErrorNote, Field } from '../components/ui'

export default function AuthPage({ mode }) {
  const { portal } = useParams()
  const { t, lang } = useI18n()
  const { startSession, user } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [form, setForm] = useState({ email: '', password: '', display_name: '', phone: '', business_name: '', code: '', new_password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState('')
  const [resetStage, setResetStage] = useState(1)

  if (!['worker', 'employer'].includes(portal)) return <Navigate to="/" replace />
  if (user && user.role === portal) return <Navigate to={`/${portal}`} replace />

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const fieldErr = (name) => error?.details?.fields?.find((f) => f.field === name)?.message

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null); setInfo('')
    try {
      if (mode === 'login') {
        const d = await api('/api/auth/login', { method: 'POST', body: { email: form.email, password: form.password, portal } })
        startSession(d.token, d.user)
        nav(loc.state?.from || `/${portal}`, { replace: true })
      } else if (mode === 'register') {
        const body = { email: form.email, password: form.password, display_name: form.display_name, preferred_language: lang }
        if (form.phone.trim()) body.phone = form.phone.trim()
        if (portal === 'employer' && form.business_name.trim()) body.business_name = form.business_name.trim()
        const d = await api(`/api/auth/register/${portal}`, { method: 'POST', body })
        startSession(d.token, d.user)
        nav(`/${portal}`, { replace: true })
      } else if (resetStage === 1) {
        const d = await api('/api/auth/forgot-password', { method: 'POST', body: { email: form.email } })
        setInfo(d.status)
        setResetStage(2)
      } else {
        const d = await api('/api/auth/reset-password', { method: 'POST', body: { email: form.email, code: form.code, new_password: form.new_password } })
        setInfo(d.status)
        setTimeout(() => nav(`/${portal}/sign-in`), 1200)
      }
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const title = mode === 'login' ? t('signIn') : mode === 'register' ? t('register') : t('forgotPassword')
  const portalName = portal === 'worker' ? t('workerPortal') : t('employerPortal')
  return (
    <div className="narrow">
      <div className="portal-switch" role="tablist" aria-label="Portal">
        {['worker', 'employer'].map((p) => (
          <Link key={p} role="tab" aria-selected={p === portal} className={p === portal ? 'active' : ''} to={`/${p}/${mode === 'forgot' ? 'sign-in' : mode === 'login' ? 'sign-in' : 'register'}`}>
            {p === 'worker' ? t('workerPortal') : t('employerPortal')}
          </Link>
        ))}
      </div>
      <form className="card" onSubmit={submit} noValidate={false}>
        <h1>{title} <span className="muted">· {portalName}</span></h1>
        {mode === 'register' && (
          <Field label={t('yourName')} id="name">
            <input id="name" required maxLength={100} autoComplete="name" value={form.display_name} onChange={set('display_name')} />
          </Field>
        )}
        <Field label={t('email')} id="email">
          <input id="email" type="email" required autoComplete="email" value={form.email} onChange={set('email')} aria-invalid={Boolean(fieldErr('email'))} />
        </Field>
        {mode !== 'forgot' && (
          <Field label={t('password')} id="pw" hint={mode === 'register' ? t('passwordHint') : null}>
            <input id="pw" type="password" required minLength={mode === 'register' ? 8 : 1} autoComplete={mode === 'register' ? 'new-password' : 'current-password'} value={form.password} onChange={set('password')} />
          </Field>
        )}
        {mode === 'register' && (
          <>
            <Field label={t('phoneOptional')} id="phone">
              <input id="phone" type="tel" inputMode="tel" maxLength={20} autoComplete="tel" value={form.phone} onChange={set('phone')} />
            </Field>
            {portal === 'employer' && (
              <Field label={t('businessNameOptional')} id="biz">
                <input id="biz" maxLength={150} value={form.business_name} onChange={set('business_name')} />
              </Field>
            )}
          </>
        )}
        {mode === 'forgot' && resetStage === 2 && (
          <>
            <Field label={t('resetCode')} id="code">
              <input id="code" inputMode="numeric" pattern="\d{6}" maxLength={6} required value={form.code} onChange={set('code')} />
            </Field>
            <Field label={t('newPassword')} id="npw" hint={t('passwordHint')}>
              <input id="npw" type="password" minLength={8} required autoComplete="new-password" value={form.new_password} onChange={set('new_password')} />
            </Field>
          </>
        )}
        <ErrorNote error={error} />
        {info && <p className="note note-ok" role="status">{info}</p>}
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? t('loading') : mode === 'forgot' ? (resetStage === 1 ? t('sendResetCode') : t('changePassword')) : title}
        </button>
        <div className="row between small">
          {mode === 'login' && <Link to={`/${portal}/register`}>{t('noAccount')}</Link>}
          {mode === 'register' && <Link to={`/${portal}/sign-in`}>{t('haveAccount')}</Link>}
          {mode === 'login' && <Link to={`/${portal}/forgot`}>{t('forgotPassword')}</Link>}
          {mode === 'forgot' && <Link to={`/${portal}/sign-in`}>{t('backToSignIn')}</Link>}
        </div>
      </form>
    </div>
  )
}
