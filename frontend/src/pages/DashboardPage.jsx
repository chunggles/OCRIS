import { useCallback } from 'react'
import { useApp } from '../context/AppContext'
import { Card, StatCard, Badge, Alert, Btn, StatusBanner, EmptyState, PageHeader } from '../components/ui/index'
import { recordsAPI, analyticsAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { formatDate, formatLongDate, isNA, plural } from '../utils/format'

const RECENT_LIMIT = 6

function RecentUploads({ records, loading, onRefresh }) {
  const { nav } = useApp()
  if (loading) return <StatusBanner loading/>
  if (records.length === 0) {
    return (
      <EmptyState icon="📋" action={<Btn variant="primary" onClick={() => nav('upload')}>Upload Form 137</Btn>}>
        No records yet. Upload your first Form 137 to get started.
      </EmptyState>
    )
  }
  return (
    <>
      <table>
        <thead><tr><th>Pupil</th><th>Grade</th><th>Uploaded</th><th>Status</th><th></th></tr></thead>
        <tbody>
          {records.slice(0, RECENT_LIMIT).map((r, i) => {
            const validated = !isNA(r.general_average)
            return (
              <tr key={r.record_id || i}>
                <td className="col-name">{r.pupil_name || '—'}</td>
                <td>{r.grade_level || '—'}</td>
                <td>{formatDate(r.created_at, { month: 'short', day: 'numeric' })}</td>
                <td><Badge type={validated ? 'b-green' : 'b-amber'}>{validated ? 'Validated' : 'Pending'}</Badge></td>
                <td>
                  {validated
                    ? <Btn size="sm" onClick={() => nav('detail', { recordId: r.record_id })}>View</Btn>
                    : <Btn variant="primary" size="sm" onClick={() => nav('upload')}>Validate</Btn>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div className="btn-row" style={{ marginTop: 12 }}>
        <Btn size="sm" onClick={() => nav('records')}>View all records →</Btn>
        <Btn size="sm" onClick={onRefresh}>↻ Refresh</Btn>
      </div>
    </>
  )
}

export default function DashboardPage() {
  const { nav } = useApp()
  const fetchRecords   = useCallback(() => recordsAPI.list({ page: 1 }), [])
  const fetchAnalytics = useCallback(() => analyticsAPI.dashboard({}), [])
  const { data: recData, loading, error, refetch } = useFetch(fetchRecords)
  const { data: anaData } = useFetch(fetchAnalytics)

  const records = recData?.results || []
  const total   = recData?.total || 0
  const pending = records.filter(r => isNA(r.general_average)).length
  const flags   = anaData?.intervention_flags?.length ?? 0

  return (
    <div>
      <PageHeader title="Dashboard" sub={formatLongDate()}/>
      <StatusBanner error={error} onRetry={refetch}/>
      <div className="stats">
        <StatCard value={total.toLocaleString()} label="Digitized records"  color="blue"/>
        <StatCard value={pending}                label="Pending validation" color="amber"/>
        <StatCard value={flags}                  label="Intervention flags" color="rose"/>
      </div>
      <div className="g-3-2">
        <Card title="Recent uploads">
          <RecentUploads records={records} loading={loading} onRefresh={refetch}/>
        </Card>
        <div>
          {pending > 0 && (
            <Alert type="amber">
              <strong>{plural(pending, 'scan')} pending validation.</strong>
              <div style={{ marginTop: 8 }}><Btn variant="primary" size="sm" onClick={() => nav('upload')}>Go to Upload</Btn></div>
            </Alert>
          )}
          {flags > 0 && (
            <Alert type="rose">
              <strong>{plural(flags, 'intervention flag')} active.</strong>
              <div style={{ marginTop: 8 }}><Btn size="sm" onClick={() => nav('analytics')}>View analytics</Btn></div>
            </Alert>
          )}
          {!loading && records.length > 0 && pending === 0 && flags === 0 && (
            <Alert type="green"><strong>All clear.</strong> No pending validations or intervention flags.</Alert>
          )}
        </div>
      </div>
    </div>
  )
}
