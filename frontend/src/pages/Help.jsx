import { Link } from 'react-router-dom'
import { useI18n } from '../i18n'

const SECTIONS = [
  ['helpWhatStored', 'helpWhatStoredText'],
  ['helpShared', 'helpSharedText'],
  ['helpAi', 'helpAiText'],
  ['helpChecks', 'helpChecksText'],
  ['helpVoice', 'helpVoiceText'],
  ['helpDelete', 'helpDeleteText'],
]

export default function Help() {
  const { t } = useI18n()
  return (
    <div className="narrow-page stack">
      <h1>{t('helpTitle')}</h1>
      {SECTIONS.map(([h, p]) => (
        <section key={h} className="card">
          <h2>{t(h)}</h2>
          <p>{t(p)}</p>
        </section>
      ))}
      <p className="note">{t('helpNotLegal')}</p>
      <Link to="/guide">{t('guideLink')} →</Link>
    </div>
  )
}
