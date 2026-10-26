import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { ErrorNote, Money, StatusBadge, VerifyEmailCard, formatDate } from '../components/ui'
import { Stat } from './WorkerHome'

export default function EmployerInbox() {
  const { user } = useAuth()
  const { t } = useI18n()
  const [filter, setFilter] = useState('attention')
  const [data, setData] = useState(null)
  const [all, setAll] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    if (!user.email_verified) return
    setError(null); setData(null)
    api(`/api/employer/claims?filter=${filter}`).then(setData).catch(setError)
  }, [filter, user.email_verified])
  useEffect(() => {
    if (!user.email_verified) return
    Promise.all([api('/api/employer/claims?filter=all&limit=100'), api('/api/employer/claims?filter=attention&limit=100')])
      .then(([a, b]) => setAll({ total: a.total, attention: b.total, resolved: a.items.filter((c) => c.status === 'resolved').length }))
      .catch(() => {})
  }, [user.email_verified])

  return (
    <div className="stack-l">
      <section className="page-hero">
        <div>
          <p className="eyebrow">{t('eyebrowEmployer')}</p>
          <h1 className="hero-title">{t('hello', { name: user.business_name || user.display_name })}</h1>
          <p className="lead muted">{t('employerLead')}</p>
        </div>
      </section>
      <VerifyEmailCard />
      {user.email_verified && all && (
        <div className="stats">
          <Stat label={t('statReceived')} value={all.total} tone="blue" />
          <Stat label={t('statAttention')} value={all.attention} tone="amber" />
          <Stat label={t('statResolved')} value={all.resolved} tone="green" />
        </div>
      )}
      {user.email_verified && (
        <section className="card">
          <div className="row between wrap">
            <h2>{t('inbox')}</h2>
            <div className="segmented" role="tablist">
              {['attention', 'all'].map((f) => (
                <button key={f} type="button" role="tab" aria-selected={filter === f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>
                  {f === 'attention' ? t('needsAttention') : t('all')}
                </button>
              ))}
            </div>
          </div>
          <ErrorNote error={error} />
          {!data && !error && <p className="muted">{t('loading')}</p>}
          {data && data.items.length === 0 && <p className="empty">{t('noEmployerClaims', { email: user.email })}</p>}
          {data && data.items.length > 0 && (
            <ul className="claim-list">
              {data.items.map((c) => (
                <li key={c.id}>
                  <Link to={`/employer/claims/${c.id}`} className="claim-row">
                    <div>
                      <div className="row gap-s"><StatusBadge status={c.status} issue={c.issue_type} />{c.issue_type && c.issue_type !== 'wages' && <span className="tag">{t(`issue_${c.issue_type}`)}</span>}{c.unread > 0 && <span className="pill">{t('unreadUpdates', { n: c.unread })}</span>}</div>
                      <strong>{t('fromWorker', { name: c.worker_name })}</strong>
                      <div className="muted small">{c.reference} · {formatDate(c.submitted_at)}</div>
                    </div>
                    <div className="right">{c.amount_claimed && <strong><Money value={c.amount_claimed} /></strong>}</div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
