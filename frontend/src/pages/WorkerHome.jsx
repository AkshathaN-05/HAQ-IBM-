import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { ErrorNote, Money, StatusBadge, VerifyEmailCard } from '../components/ui'

export function ClaimRow({ c }) {
  const { t } = useI18n()
  const to = c.status === 'draft' ? `/worker/claims/${c.id}/edit` : `/worker/claims/${c.id}`
  return (
    <li>
      <Link to={to} className="claim-row">
        <div>
          <div className="row gap-s"><StatusBadge status={c.status} />{c.unread > 0 && <span className="pill">{t('unreadUpdates', { n: c.unread })}</span>}</div>
          <strong>{c.employer_name || c.reference}</strong>
          <p className="muted small clamp">{c.preview}</p>
        </div>
        <div className="right">
          {c.amount_claimed && <strong><Money value={c.amount_claimed} /></strong>}
          <div className="muted small">{c.reference}</div>
        </div>
      </Link>
    </li>
  )
}

export default function WorkerHome() {
  const { user } = useAuth()
  const { t } = useI18n()
  const [claims, setClaims] = useState(null)
  const [error, setError] = useState(null)
  const load = () => { setError(null); api('/api/claims?limit=5').then(setClaims).catch(setError) }
  useEffect(load, [])

  return (
    <div className="stack">
      <h1 className="greeting">{t('hello', { name: user.display_name })}</h1>
      <VerifyEmailCard />
      <Link to="/worker/new" className="big-action">
        <span className="big-action-icon" aria-hidden="true">🎙️</span>
        <span>
          <span className="big-action-title">{t('tellUs')}</span>
          <span className="big-action-sub">{t('tellUsSub')}</span>
        </span>
      </Link>
      <nav className="tile-grid" aria-label="Worker menu">
        <Link to="/worker/claims" className="tile"><span aria-hidden="true">📂</span>{t('myClaims')}</Link>
        <Link to="/worker/records" className="tile"><span aria-hidden="true">🗓️</span>{t('myWorkRecords')}</Link>
        <Link to="/wages" className="tile"><span aria-hidden="true">🧮</span>{t('wageCalculator')}</Link>
        <Link to="/help" className="tile"><span aria-hidden="true">❓</span>{t('help')}</Link>
      </nav>
      <section>
        <h2>{t('myClaims')}</h2>
        <ErrorNote error={error} onRetry={load} />
        {!claims && !error && <p className="muted">{t('loading')}</p>}
        {claims && claims.items.length === 0 && <p className="empty">{t('noClaims')}</p>}
        {claims && claims.items.length > 0 && <ul className="claim-list">{claims.items.map((c) => <ClaimRow key={c.id} c={c} />)}</ul>}
        {claims && claims.total > 5 && <Link to="/worker/claims">{t('myClaims')} →</Link>}
      </section>
    </div>
  )
}
