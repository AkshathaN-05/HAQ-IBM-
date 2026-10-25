import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { ErrorNote, Money, StatusBadge, VerifyEmailCard, formatDate } from '../components/ui'

export default function EmployerInbox() {
  const { user } = useAuth()
  const { t } = useI18n()
  const [filter, setFilter] = useState('attention')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    if (!user.email_verified) return
    setError(null); setData(null)
    api(`/api/employer/claims?filter=${filter}`).then(setData).catch(setError)
  }, [filter, user.email_verified])

  return (
    <div className="stack">
      <h1 className="greeting">{t('hello', { name: user.business_name || user.display_name })}</h1>
      <VerifyEmailCard />
      {user.email_verified && (
        <section>
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
                      <div className="row gap-s"><StatusBadge status={c.status} />{c.unread > 0 && <span className="pill">{t('unreadUpdates', { n: c.unread })}</span>}</div>
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
