import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { formatDate, LanguagePicker } from './ui'

function Notifications() {
  const { user } = useAuth()
  const { t } = useI18n()
  const nav = useNavigate()
  const loc = useLocation()
  const [data, setData] = useState({ items: [], unread: 0 })
  const [open, setOpen] = useState(false)

  const load = useCallback(async () => {
    try { setData(await api('/api/notifications')) } catch { /* shown as no updates */ }
  }, [])
  useEffect(() => {
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [load, loc.pathname, user?.id])

  const go = (n) => {
    setOpen(false)
    if (n.claim_id) nav(user.role === 'worker' ? `/worker/claims/${n.claim_id}` : `/employer/claims/${n.claim_id}`)
  }
  const readAll = async () => { await api('/api/notifications/read-all', { method: 'POST' }).catch(() => {}); load() }

  return (
    <div className="notif">
      <button type="button" className="icon-btn" aria-expanded={open} aria-label={`${t('notifications')} (${data.unread})`} onClick={() => setOpen((o) => !o)}>
        <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 0 0-5.5-6.84V3.5a1.5 1.5 0 0 0-3 0v.66A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2Z"/></svg>
        {data.unread > 0 && <span className="dot-count">{data.unread}</span>}
      </button>
      {open && (
        <div className="notif-panel" role="dialog" aria-label={t('notifications')}>
          <div className="row between">
            <strong>{t('notifications')}</strong>
            {data.unread > 0 && <button type="button" className="link-btn" onClick={readAll}>{t('markAllRead')}</button>}
          </div>
          {data.items.length === 0 && <p className="muted">{t('noNotifications')}</p>}
          <ul>
            {data.items.map((n) => (
              <li key={n.id}>
                <button type="button" className={n.read_at ? 'notif-item' : 'notif-item unread'} onClick={() => go(n)}>
                  <span>{t(`n_${n.type}`)}</span>
                  <span className="muted small">{n.reference} · {formatDate(n.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function Layout({ children }) {
  const { user, signOut } = useAuth()
  const { t } = useI18n()
  const nav = useNavigate()
  const home = user ? (user.role === 'worker' ? '/worker' : '/employer') : '/'
  const out = async (all) => {
    if (all) await api('/api/auth/logout-all', { method: 'POST' }).catch(() => {})
    signOut()
    nav('/')
  }
  return (
    <div className="shell">
      <a href="#main" className="skip">Skip to content</a>
      <header className="topbar">
        <Link to={home} className="brand" aria-label="HAQ home">
          <span className="brand-mark" aria-hidden="true">ह</span>
          <span className="brand-name">HAQ</span>
          {user && <span className="portal-tag">{user.role === 'worker' ? t('workerPortal') : t('employerPortal')}</span>}
        </Link>
        <div className="topbar-right">
          <LanguagePicker compact />
          {user && <Notifications />}
          {user && (
            <details className="menu">
              <summary aria-label="Account menu">{user.display_name.slice(0, 1).toUpperCase()}</summary>
              <div className="menu-panel">
                <p className="small muted">{user.email}</p>
                <Link to="/help">{t('help')}</Link>
                <button type="button" className="link-btn" onClick={() => out(false)}>{t('signOut')}</button>
                <button type="button" className="link-btn" onClick={() => out(true)}>{t('signOutAll')}</button>
              </div>
            </details>
          )}
        </div>
      </header>
      <main id="main" className="content">{children}</main>
      <footer className="footer small muted">
        <span>HAQ</span> · <Link to="/help">{t('help')}</Link>
      </footer>
    </div>
  )
}
