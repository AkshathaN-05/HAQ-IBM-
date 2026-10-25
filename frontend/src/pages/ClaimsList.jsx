import { useEffect, useState } from 'react'
import { api } from '../api'
import { useI18n } from '../i18n'
import { ErrorNote } from '../components/ui'
import { ClaimRow } from './WorkerHome'

const PAGE = 20

export default function ClaimsList() {
  const { t } = useI18n()
  const [data, setData] = useState(null)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState(null)
  useEffect(() => { api(`/api/claims?limit=${PAGE}&offset=${offset}`).then(setData).catch(setError) }, [offset])
  return (
    <div className="stack">
      <h1>{t('myClaims')}</h1>
      <ErrorNote error={error} />
      {data && data.items.length === 0 && <p className="empty">{t('noClaims')}</p>}
      {data && <ul className="claim-list">{data.items.map((c) => <ClaimRow key={c.id} c={c} />)}</ul>}
      {data && data.total > PAGE && (
        <div className="row between">
          <button className="btn btn-ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>{t('back')}</button>
          <button className="btn btn-ghost" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>{t('next')}</button>
        </div>
      )}
    </div>
  )
}
