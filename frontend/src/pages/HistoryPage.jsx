import { useState, useCallback } from 'react'
import { Card, Badge, Btn, StatusBanner, EmptyState, Pager, PageHeader } from '../components/ui/index'
import DownloadScanBtn from '../components/ui/DownloadScanBtn'
import { ocrAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { formatDateTime } from '../utils/format'

const OUTCOME_BADGES = { saved: 'b-green', rejected: 'b-rose' }

const confidenceColor = (conf) => {
  if (conf === undefined || conf === null) return 'text-3'
  return conf >= 90 ? 'green' : conf >= 70 ? 'amber' : 'rose'
}

function ScanRow({ scan: r }) {
  const outcome = r.outcome || 'pending'
  const flags   = r.flags_count ?? 0
  return (
    <tr>
      <td className="mono" style={{ fontSize: 10 }}>{r.scan_id || '—'}</td>
      <td className="col-name">{r.pupil_name || '—'}</td>
      <td>{r.grade_level || '—'}</td>
      <td>{r.uploaded_by || '—'}</td>
      <td style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{formatDateTime(r.created_at)}</td>
      <td style={{ color: `var(--${confidenceColor(r.overall_conf)})`, fontWeight: 700 }}>
        {r.overall_conf !== undefined ? `${r.overall_conf}%` : '—'}
      </td>
      <td><Badge type={flags > 0 ? 'b-amber' : 'b-green'}>{flags}</Badge></td>
      <td><Badge type={OUTCOME_BADGES[outcome] || 'b-amber'}>{outcome}</Badge></td>
      <td>{r.filename ? <DownloadScanBtn scanId={r.scan_id}/> : '—'}</td>
    </tr>
  )
}

export default function HistoryPage() {
  const [page, setPage] = useState(1)
  const fetchHistory = useCallback(() => ocrAPI.history(page), [page])
  const { data, loading, error, refetch } = useFetch(fetchHistory)
  const rows  = data?.results || []
  const total = data?.total || 0

  return (
    <div>
      <PageHeader title="Scan History"/>
      <StatusBanner error={error} onRetry={refetch}/>
      <Card
        title={`${total.toLocaleString()} total scans`}
        action={<Btn size="sm" onClick={refetch}>↻ Refresh</Btn>}
      >
        {loading ? <StatusBanner loading/> : rows.length === 0 ? (
          <EmptyState icon="🖨️">
            {error ? 'Could not load scan history.' : 'No scans yet.'}
          </EmptyState>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Scan ID</th><th>Pupil</th><th>Grade</th><th>Uploaded by</th><th>Date / Time</th>
                  <th>OCR confidence</th><th>Flags</th><th>Outcome</th><th>File</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => <ScanRow key={r.scan_id || i} scan={r}/>)}
              </tbody>
            </table>
            <Pager page={page} total={total} onChange={setPage}/>
          </>
        )}
      </Card>
    </div>
  )
}
