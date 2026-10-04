import { useCallback } from 'react'
import { useApp } from '../context/AppContext'
import { Card, Btn, InfoRow, StatusBanner, EmptyState, PageHeader, RemarksBadge } from '../components/ui/index'
import DownloadScanBtn from '../components/ui/DownloadScanBtn'
import { recordsAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { formatDateTime, isNA, plural, NA, PASSING_GRADE } from '../utils/format'

const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4']

function GradesTable({ grades }) {
  const subjects = Object.keys(grades)
  if (subjects.length === 0) return <EmptyState>No grades stored for this record.</EmptyState>
  return (
    <div style={{ overflowX: 'auto' }}>
      <table>
        <thead>
          <tr>
            <th>Subject</th>
            {QUARTERS.map(q => <th key={q} className="center">{q}</th>)}
            <th className="center">Final</th>
          </tr>
        </thead>
        <tbody>
          {subjects.map(subject => {
            const g = grades[subject] || {}
            const failing = !isNA(g.final) && parseFloat(g.final) < PASSING_GRADE
            return (
              <tr key={subject}>
                <td className="col-name">{subject}</td>
                {QUARTERS.map(q => (
                  <td key={q} className="center" style={{ color: isNA(g[q]) ? 'var(--text-3)' : 'var(--text)' }}>
                    {isNA(g[q]) ? NA : g[q]}
                  </td>
                ))}
                <td className="center" style={{ fontWeight: 700, color: isNA(g.final) ? 'var(--text-3)' : failing ? 'var(--rose)' : 'var(--text)' }}>
                  {isNA(g.final) ? NA : g.final}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function CorrectionsCard({ corrections }) {
  const entries = Object.entries(corrections || {})
  if (entries.length === 0) return null
  return (
    <Card title="Manual corrections" meta={`${plural(entries.length, 'field')} corrected during validation`}>
      <table>
        <thead><tr><th>Field</th><th>Corrected value</th></tr></thead>
        <tbody>
          {entries.map(([field, value]) => (
            <tr key={field}><td>{field}</td><td style={{ fontWeight: 700 }}>{value}</td></tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

export default function RecordDetailPage() {
  const { nav, navParams } = useApp()
  const recordId = navParams?.recordId

  const fetchRecord = useCallback(() => (recordId ? recordsAPI.get(recordId) : Promise.resolve(null)), [recordId])
  const { data: r, loading, error, refetch } = useFetch(fetchRecord)

  const backButton = <Btn onClick={() => nav('records')}>← Back to Records</Btn>
  const header = (
    <PageHeader
      title="Record Detail"
      sub={recordId && <span className="mono">{recordId}</span>}
    />
  )

  if (!recordId) {
    return (
      <div>
        {header}
        <Card>
          <EmptyState icon="📄" action={<Btn variant="primary" onClick={() => nav('records')}>Go to Records</Btn>}>
            Select a record from the Records page to view it here.
          </EmptyState>
        </Card>
      </div>
    )
  }
  if (loading) return <div>{header}<StatusBanner loading/></div>
  if (error || !r) {
    return <div>{header}<StatusBanner error={error || 'Record not found.'} onRetry={refetch}/>{backButton}</div>
  }

  const grades = r.grades || {}
  const subjectCount = Object.keys(grades).length

  return (
    <div>
      {header}
      <div className="btn-row" style={{ marginBottom: 12 }}>
        {backButton}
        <DownloadScanBtn scanId={r.scan_id} size="" variant="primary" label="Download original form"/>
      </div>

      <div className="grid-auto">
        <Card title="Pupil information">
          <InfoRow label="Pupil name">{r.pupil_name || '—'}</InfoRow>
          <InfoRow label="LRN"><span className="mono">{r.lrn || '—'}</span></InfoRow>
          <InfoRow label="Grade level">{r.grade_level || '—'}</InfoRow>
          <InfoRow label="Section">{r.section || '—'}</InfoRow>
          <InfoRow label="School year">{r.school_year || '—'}</InfoRow>
          {r.class_adviser && <InfoRow label="Class adviser">{r.class_adviser}</InfoRow>}
        </Card>
        <Card title="Summary">
          <InfoRow label="General average"><strong>{isNA(r.general_average) ? '—' : r.general_average}</strong></InfoRow>
          <InfoRow label="Remarks"><RemarksBadge remarks={r.remarks}/></InfoRow>
          <InfoRow label="Uploaded by">{r.uploaded_by || '—'}</InfoRow>
          <InfoRow label="Created">{formatDateTime(r.created_at)}</InfoRow>
          <InfoRow label="Last updated">{formatDateTime(r.updated_at)}</InfoRow>
          {r.scan_id && <InfoRow label="Scan ID"><span className="mono-sm">{r.scan_id}</span></InfoRow>}
        </Card>
      </div>

      <Card title="Grades" meta={plural(subjectCount, 'subject')}>
        <GradesTable grades={grades}/>
      </Card>

      <CorrectionsCard corrections={r.corrections}/>
    </div>
  )
}
