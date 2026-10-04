import { useState, useCallback } from 'react'
import { AUDIT_BADGES } from '../data/constants'
import { Card, Badge, Btn, StatusBanner, EmptyState, Pager, PageHeader } from '../components/ui/index'
import { auditAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { formatDateTime } from '../utils/format'

// One-line summary of an entry's details object
const describe = (d = {}) => [
  d.pupil && `Pupil: ${d.pupil}`,
  d.grade && `Grade: ${d.grade}`,
  d.new_user && `New user: ${d.new_user} (${d.role})`,
  d.deleted_user && `Deleted user: ${d.deleted_user} (${d.role})`,
  d.confidence !== undefined && `Conf: ${d.confidence}%`,
  d.corrections !== undefined && `Corrections: ${d.corrections}`,
].filter(Boolean).join(' · ')

export default function AuditPage() {
  const [page, setPage] = useState(1)
  const fetchAudit = useCallback(() => auditAPI.list(page), [page])
  const { data, loading, error, refetch } = useFetch(fetchAudit)
  const rows  = data?.results || []
  const total = data?.total || 0

  return (
    <div>
      <PageHeader title="Audit Log"/>
      <StatusBanner error={error} onRetry={refetch}/>
      <Card
        title={`${total.toLocaleString()} log entries`}
        action={<Btn size="sm" onClick={refetch}>↻ Refresh</Btn>}
      >
        {loading ? <StatusBanner loading/> : rows.length === 0 ? (
          <EmptyState icon="📋">
            {error ? 'Could not load the audit log.' : 'No activity recorded yet.'}
          </EmptyState>
        ) : (
          <>
            <table>
              <thead>
                <tr><th>Action</th><th>User</th><th>Timestamp</th><th>Details</th><th>Record / Scan ID</th></tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const d = r.details || {}
                  return (
                    <tr key={i}>
                      <td><Badge type={AUDIT_BADGES[r.action] || 'b-grey'}>{r.action}</Badge></td>
                      <td style={{ fontWeight: 500, color: 'var(--text)' }}>{r.user || '—'}</td>
                      <td style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{formatDateTime(r.timestamp)}</td>
                      <td className="text-muted" style={{ fontSize: 11 }}>{describe(d) || '—'}</td>
                      <td className="mono" style={{ fontSize: 10 }}>{d.record_id || d.scan_id || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Pager page={page} total={total} onChange={setPage}/>
          </>
        )}
      </Card>
    </div>
  )
}
