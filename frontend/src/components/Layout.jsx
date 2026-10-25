import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { formatDate, LanguagePicker } from './ui'
import Icon from './Icon'

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
  const loc = useLocation()
  const home = user ? (user.role === 'worker' ? '/worker' : '/employer') : '/'
  const out = () => { signOut(); nav('/') }
  const atHome = loc.pathname === home
  return (
    <div className="shell">
      <a href="#main" className="skip">Skip to content</a>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to={home} className="brand" aria-label="HAQ home">
            <span className="brand-mark" aria-hidden="true"><Icon name="scale" size={24} /></span>
            <span className="brand-text">
              <span className="brand-name">HAQ</span>
              <span className="brand-tag">{t('appTagline')}</span>
            </span>
          </Link>
          <div className="topbar-right">
            <LanguagePicker compact />
            {user && <span className="top-email">{user.email}</span>}
            {user && <span className="portal-tag">{user.role === 'worker' ? t('workerPortal') : t('employerPortal')}</span>}
            {user && <Notifications />}
            {user && !atHome && <Link to={home} className="btn btn-ghost btn-small top-btn top-home">← {t('home')}</Link>}
            {user && <button type="button" className="btn btn-ghost btn-small top-btn" onClick={out}>{t('signOut')}</button>}
          </div>
        </div>
      </header>
      <main id="main" className="content">{children}</main>
      <footer className="footer small muted">
        <span>HAQ</span> · <Link to="/help">{t('help')}</Link>
      </footer>
    </div>
  )
}
