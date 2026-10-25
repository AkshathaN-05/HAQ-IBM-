import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { ErrorNote, Money, StatusBadge, VerifyEmailCard } from '../components/ui'
import Icon from '../components/Icon'

export function ClaimRow({ c }) {
  const { t } = useI18n()
  const to = c.status === 'draft' ? `/worker/claims/${c.id}/edit` : `/worker/claims/${c.id}`
  return (
    <li>
      <Link to={to} className="claim-row">
        <div>
          <div className="row gap-s"><StatusBadge status={c.status} />{c.issue_type && c.issue_type !== 'wages' && <span className="tag">{t(`issue_${c.issue_type}`)}</span>}{c.unread > 0 && <span className="pill">{t('unreadUpdates', { n: c.unread })}</span>}</div>
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

export function Stat({ label, value, tone }) {
  return (
    <div className={`stat${tone ? ` stat-${tone}` : ''}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{String(value).padStart(2, '0')}</span>
    </div>
  )
}

const CLOSED = ['resolved', 'withdrawn']

export default function WorkerHome() {
  const { user } = useAuth()
  const { t } = useI18n()
  const [claims, setClaims] = useState(null)
  const [error, setError] = useState(null)
  const load = () => { setError(null); api('/api/claims?limit=100').then(setClaims).catch(setError) }
  useEffect(load, [])

  const items = claims?.items || []
  const active = items.filter((c) => c.status !== 'draft' && !CLOSED.includes(c.status)).length
  const drafts = items.filter((c) => c.status === 'draft').length
  const resolved = items.filter((c) => c.status === 'resolved').length

  return (
    <div className="stack-l">
      <section className="page-hero">
        <div>
          <p className="eyebrow">{t('eyebrowWorker')}</p>
          <h1 className="hero-title">{t('hello', { name: user.display_name })}</h1>
          <p className="lead muted">{t('workerLead')}</p>
        </div>
      </section>
      <VerifyEmailCard />
      {claims && (
        <div className="stats">
          <Stat label={t('statActive')} value={active} tone="blue" />
          <Stat label={t('statDrafts')} value={drafts} tone="amber" />
          <Stat label={t('statResolved')} value={resolved} tone="green" />
        </div>
      )}
      <div className="home-grid">
        <section className="card">
          <div className="row between wrap">
            <h2>{t('recentClaims')}</h2>
            {claims && claims.total > 0 && <Link to="/worker/claims" className="small">{t('myClaims')} →</Link>}
          </div>
          <ErrorNote error={error} onRetry={load} />
          {!claims && !error && <p className="muted">{t('loading')}</p>}
          {claims && items.length === 0 && <p className="empty">{t('noClaims')}</p>}
          {items.length > 0 && <ul className="claim-list">{items.slice(0, 6).map((c) => <ClaimRow key={c.id} c={c} />)}</ul>}
        </section>
        <aside className="stack">
          <Link to="/worker/new?type=wages" className="big-action">
            <span className="big-action-icon" aria-hidden="true"><Icon name="mic" size={30} /></span>
            <span>
              <span className="big-action-title">{t('homeWagesTitle')}</span>
              <span className="big-action-sub">{t('homeWagesSub')}</span>
            </span>
          </Link>
          <Link to="/worker/new?type=problem" className="big-action big-action-alt">
            <span className="big-action-icon" aria-hidden="true"><Icon name="alert" size={30} /></span>
            <span>
              <span className="big-action-title">{t('homeOtherTitle')}</span>
              <span className="big-action-sub">{t('homeOtherSub')}</span>
            </span>
          </Link>
          <nav className="card" aria-label="Worker menu">
            <h2>{t('quickLinks')}</h2>
            <div className="tile-grid">
              <Link to="/worker/claims" className="tile"><Icon name="folder" size={24} />{t('myClaims')}</Link>
              <Link to="/worker/records" className="tile"><Icon name="calendar" size={24} />{t('myWorkRecords')}</Link>
              <Link to="/guide" className="tile"><Icon name="route" size={24} />{t('guideTitle')}</Link>
              <Link to="/help" className="tile"><Icon name="help" size={24} />{t('help')}</Link>
            </div>
          </nav>
        </aside>
      </div>
    </div>
  )
}
