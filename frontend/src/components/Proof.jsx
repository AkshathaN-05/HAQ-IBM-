import { useState } from 'react'
import { openProtectedFile, viewProtectedFile } from '../api'
import { useI18n } from '../i18n'
import { formatDate } from './ui'
import Icon from './Icon'


function size(n) {
  if (!n && n !== 0) return ''
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`
}

export function ProofItem({ e, showText, showShared, onError }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const hasText = showText && e.extracted_text
  const media = e.kind === 'audio' || e.kind === 'video'
  return (
    <li className="proof">
      <div className="proof-head">
        <span className="proof-icon" aria-hidden="true"><Icon name={['audio', 'video', 'image', 'document'].includes(e.kind) ? e.kind : 'clip'} /></span>
        <div className="proof-name">
          <strong>{e.label ? `${e.label}. ` : ''}{e.original_name}</strong>
          <span className="muted small">
            {t(`kind_${e.kind}`)} · {size(e.size_bytes)}
            {showShared && <> · {e.shared_with_employer ? t('sharedTag') : t('privateTag')}</>}
          </span>
        </div>
        <div className="proof-actions">
          {hasText && (
            <button type="button" className="btn btn-small btn-ghost" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
              {open ? t('hideText') : (media ? t('showHeard') : t('showRead'))}
            </button>
          )}
          <button type="button" className="btn btn-small btn-ghost" onClick={() => viewProtectedFile(e.id, e.mime_type).catch(onError)}>{t('openFile')}</button>
          <button type="button" className="btn btn-small btn-ghost" onClick={() => openProtectedFile(e.id, e.original_name).catch(onError)}>{t('saveFile')}</button>
        </div>
      </div>
      {hasText && open && (
        <div className="proof-text">
          <p className="proof-text-title">{media ? t('audioTextTitle') : t('fileTextTitle')}</p>
          <p className="pre">{e.extracted_text}</p>
          {(e.found_amounts?.length > 0 || e.found_dates?.length > 0) && (
            <div className="suggest">
              {e.found_amounts?.map((a) => <span key={a} className="tag">₹{Number(a).toLocaleString('en-IN')}</span>)}
              {e.found_dates?.map((d) => <span key={d} className="tag">{formatDate(d)}</span>)}
            </div>
          )}
        </div>
      )}
      {showText && !e.extracted_text && e.extraction_status === 'pending' && <p className="muted small proof-note">{t('reading')}</p>}
    </li>
  )
}

export function ProofList({ evidence, showText = false, showShared = false, onError }) {
  return (
    <ul className="proof-list file-list">
      {evidence.map((e) => <ProofItem key={e.id} e={e} showText={showText} showShared={showShared} onError={onError} />)}
    </ul>
  )
}
