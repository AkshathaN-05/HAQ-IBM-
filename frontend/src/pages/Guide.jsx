import { Link } from 'react-router-dom'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'

// What a worker can do if talking through HAQ does not solve the problem.
// Kept short and general; contacts were checked against official government sources.
const STEPS = [
  {
    title: 'Give your employer a fair chance',
    body: 'Send a reply in HAQ and give your employer a few days to answer. Many problems are solved here, with a clear record for both sides.',
  },
  {
    title: 'Save your record',
    body: 'On your claim, press "Print / save record". It lists your letter, every file, message, offer and payment, with dates. Take it wherever you go for help.',
  },
  {
    title: 'Unpaid wages: go to the Labour Department',
    body: 'Visit the Labour Office in your district (Assistant Labour Commissioner), or file a complaint online on the Government of India SAMADHAN portal: samadhan.labour.gov.in.',
  },
  {
    title: 'Free legal help',
    body: 'Call the NALSA free legal aid helpline 15100, or visit the District Legal Services Authority (DLSA) at your district court. Help is free for many workers.',
  },
  {
    title: 'Sexual harassment',
    body: 'Complain to the Internal Committee at your workplace. If there is none, or your employer is the one harassing you, go to the Local Committee in your district, or use the SHe-Box portal: shebox.wcd.gov.in. Women helpline: 181.',
  },
  {
    title: 'Danger or violence',
    body: 'If you are in danger, call 112 straight away.',
  },
]

export default function Guide() {
  const { user } = useAuth()
  const { t } = useI18n()
  return (
    <div className="stack-l narrow-page">
      <section className="page-hero">
        <div>
          <p className="eyebrow">{t('help')}</p>
          <h1 className="hero-title">{t('guideTitle')}</h1>
          <p className="lead muted">HAQ helps you and your employer talk. If that does not work, you still have options.</p>
        </div>
      </section>
      <ol className="roadmap">
        {STEPS.map((s, i) => (
          <li key={s.title} className="card roadmap-step">
            <span className="roadmap-num" aria-hidden="true">{i + 1}</span>
            <div>
              <h2>{s.title}</h2>
              <p>{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="note">{t('notCourt')} Rules and offices can differ from state to state.</p>
      {user && <Link to={user.role === 'worker' ? '/worker' : '/employer'}>← {t('home')}</Link>}
    </div>
  )
}
