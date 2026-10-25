import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { LanguagePicker } from '../components/ui'
import Icon from '../components/Icon'

export default function Landing() {
  const { user, ready } = useAuth()
  const { t } = useI18n()
  if (ready && user) return <Navigate to={user.role === 'worker' ? '/worker' : '/employer'} replace />
  return (
    <div className="landing">
      <section className="hero">
        <p className="eyebrow">{t('eyebrowLanding')}</p>
        <h1>{t('appTagline')}</h1>
        <p className="lead">{t('appIntro')}</p>
        <LanguagePicker />
      </section>
      <div className="choice-grid">
        <Link to="/worker/register" className="choice choice-primary">
          <span className="choice-icon" aria-hidden="true"><Icon name="worker" size={30} /></span>
          <span className="choice-title">{t('iAmWorker')}</span>
          <span className="choice-sub">{t('iAmWorkerSub')}</span>
        </Link>
        <Link to="/employer/sign-in" className="choice">
          <span className="choice-icon" aria-hidden="true"><Icon name="building" size={30} /></span>
          <span className="choice-title">{t('iAmEmployer')}</span>
          <span className="choice-sub">{t('iAmEmployerSub')}</span>
        </Link>
      </div>
      <p className="row gap">
        <Link to="/worker/sign-in">{t('workerPortal')}: {t('signIn')}</Link>
        <Link to="/guide">{t('guideTitle')}</Link>
        <Link to="/help">{t('help')}</Link>
      </p>
      <p className="note">{t('notCourt')}</p>
    </div>
  )
}
