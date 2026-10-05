import { useState, useCallback } from 'react'
import { useApp } from '../context/AppContext'
import { GRADE_LEVELS, isStaffRole } from '../data/constants'
import { Card, Btn, StatusBanner, EmptyState, Pager, PageHeader, RemarksBadge } from '../components/ui/index'
import DownloadScanBtn from '../components/ui/DownloadScanBtn'
import { recordsAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { formatDate, isNA } from '../utils/format'
import { useRecordOptions, withExtras } from '../utils/useRecordOptions'

const PAGE_SIZE = 20
const NO_FILTERS = { grade: '', section: '', school_year: '' }

function FilterSelect({ value, onChange, allLabel, options }) {
  return (
    <select className="fld fld-auto" value={value} onChange={e => onChange(e.target.value)}>
      <option value="">{allLabel}</option>
      {options.map(o => <option key={o}>{o}</option>)}
    </select>
  )
}

function RecordRow({ record: r, onDelete }) {
  const { nav, user } = useApp()
  const hasAvg = !isNA(r.general_average)
  return (
    <tr>
      <td className="col-name">{r.pupil_name || '—'}</td>
      <td>{r.grade_level || '—'}</td>
      <td>{r.section || '—'}</td>
      <td>{r.school_year || '—'}</td>
      <td style={{ fontSize: 11 }}>{formatDate(r.created_at)}</td>
      <td style={{ fontWeight: hasAvg ? 700 : 400, color: hasAvg ? 'var(--text)' : 'var(--text-3)' }}>
        {hasAvg ? r.general_average : '—'}
      </td>
      <td><RemarksBadge remarks={r.remarks}/></td>
      <td>
        <div className="btn-row">
          <Btn size="sm" onClick={() => nav('detail', { recordId: r.record_id })} disabled={!r.record_id}>View</Btn>
          <DownloadScanBtn scanId={r.scan_id}/>
          {r.record_id && isStaffRole(user?.role) && <Btn variant="danger" size="sm" onClick={() => onDelete(r)}>Delete</Btn>}
        </div>
      </td>
    </tr>
  )
}

export default function RecordsPage() {
  const { nav } = useApp()
  const [page,    setPage]    = useState(1)
  const [filters, setFilters] = useState(NO_FILTERS)
  const options = useRecordOptions()

  const setFilter = (key, value) => { setFilters(f => ({ ...f, [key]: value })); setPage(1) }
  const clearFilters = () => { setFilters(NO_FILTERS); setPage(1) }

  const fetchRecords = useCallback(() => {
    const active = Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
    return recordsAPI.list({ ...active, page })
  }, [filters, page])
  const { data, loading, error, refetch } = useFetch(fetchRecords)

  const records = data?.results || []
  const total   = data?.total || 0

  const handleDelete = async (record) => {
    if (!window.confirm(`Delete the record for ${record.pupil_name}?\nIts scanned form is deleted too. This cannot be undone.`)) return
    try {
      await recordsAPI.delete(record.record_id)
      refetch()
    } catch {
      alert('Delete failed. Try again in a moment.')
    }
  }

  return (
    <div>
      <PageHeader title="Records"/>
      <StatusBanner error={error} onRetry={refetch}/>
      <Card>
        <div className="filter-bar">
          <FilterSelect value={filters.grade}       onChange={v => setFilter('grade', v)}       allLabel="All grades"       options={withExtras(GRADE_LEVELS, options.grade_levels)}/>
          <FilterSelect value={filters.section}     onChange={v => setFilter('section', v)}     allLabel="All sections"     options={options.sections}/>
          <FilterSelect value={filters.school_year} onChange={v => setFilter('school_year', v)} allLabel="All school years" options={options.school_years}/>
          <Btn size="sm" onClick={clearFilters}>Clear</Btn>
          <div className="btn-row" style={{ marginLeft: 'auto' }}>
            <Btn size="sm" onClick={refetch}>↻ Refresh</Btn>
            <Btn variant="primary" size="sm" onClick={() => nav('upload')}>Upload new</Btn>
          </div>
        </div>

        {loading ? <StatusBanner loading/> : records.length === 0 ? (
          <EmptyState icon="📂" action={!error && <Btn variant="primary" onClick={() => nav('upload')}>Upload Form 137</Btn>}>
            {error ? 'Could not load records.' : 'No records found. Upload a Form 137 to get started.'}
          </EmptyState>
        ) : (
          <>
            <div className="hint" style={{ marginTop: 0, marginBottom: 10 }}>
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of <strong>{total}</strong> records
            </div>
            <table>
              <thead>
                <tr>
                  <th>Pupil name</th><th>Grade</th><th>Section</th><th>School year</th>
                  <th>Uploaded</th><th>General avg</th><th>Remarks</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, i) => <RecordRow key={r.record_id || i} record={r} onDelete={handleDelete}/>)}
              </tbody>
            </table>
            <Pager page={page} total={total} size={PAGE_SIZE} onChange={setPage}/>
          </>
        )}
      </Card>
    </div>
  )
}
