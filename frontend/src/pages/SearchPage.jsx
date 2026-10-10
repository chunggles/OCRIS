import { useState } from 'react'
import { useApp } from '../context/AppContext'
import { Card, Btn, StatusBanner, EmptyState, PageHeader, RemarksBadge, SearchInput } from '../components/ui/index'
import { recordsAPI } from '../utils/api'
import PrintFormBtn from './form137/PrintFormBtn'
import { errorMessage, escapeRegExp, isNA } from '../utils/format'
import { GRADE_LEVELS } from '../data/constants'
import { useRecordOptions, withExtras } from '../utils/useRecordOptions'

// Bold every case-insensitive occurrence of `term` inside `text`
function Highlight({ text = '', term }) {
  if (!term) return text
  const parts = text.split(new RegExp(`(${escapeRegExp(term)})`, 'i'))
  return parts.map((part, i) =>
    part.toLowerCase() === term.toLowerCase() ? <strong key={i} className="highlight">{part}</strong> : part
  )
}

function ResultsTable({ results, term }) {
  const { nav } = useApp()
  return (
    <table>
      <thead>
        <tr><th>Pupil name</th><th>LRN</th><th>Grade</th><th>Section</th><th>SY</th><th>General avg</th><th>Remarks</th><th>Found in</th><th>Action</th></tr>
      </thead>
      <tbody>
        {results.map((r, i) => {
          const hasAvg = !isNA(r.general_average)
          return (
            <tr key={r.record_id || i}>
              <td className="col-name"><Highlight text={r.pupil_name} term={term}/></td>
              <td className="mono-sm">{r.lrn || '—'}</td>
              <td>{r.grade_level || '—'}</td>
              <td>{r.section || '—'}</td>
              <td>{r.school_year || '—'}</td>
              <td style={{ fontWeight: hasAvg ? 700 : 400 }}>{hasAvg ? r.general_average : '—'}</td>
              <td><RemarksBadge remarks={r.remarks}/></td>
              <td style={{ fontSize: 11 }}>{(r.matched_in || []).join(', ') || '—'}</td>
              <td>
                <div className="btn-row">
                  <Btn size="sm" onClick={() => nav('detail', { recordId: r.record_id })} disabled={!r.record_id}>View</Btn>
                  <PrintFormBtn record={r}/>
                </div>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

const NO_FILTERS = { grade: '', section: '', school_year: '' }

function FilterSelect({ value, onChange, allLabel, options }) {
  return (
    <select className="fld fld-auto" value={value} onChange={e => onChange(e.target.value)} aria-label={allLabel}>
      <option value="">{allLabel}</option>
      {options.map(o => <option key={o}>{o}</option>)}
    </select>
  )
}

export default function SearchPage() {
  const [query,   setQuery]   = useState('')
  const [filters, setFilters] = useState(NO_FILTERS)
  const [term,    setTerm]    = useState('') // the query the current results are for
  const [results, setResults] = useState(null)
  const [total,   setTotal]   = useState(0)  // how many records match; more than are shown if over the limit
  const options = useRecordOptions()
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const setFilter = (key, value) => setFilters(f => ({ ...f, [key]: value }))

  const handleSearch = async () => {
    const q = query.trim()
    if (!q) return
    setLoading(true); setError(null)
    try {
      const data = await recordsAPI.search(q, Object.fromEntries(Object.entries(filters).filter(([, v]) => v)))
      setResults(data.results || [])
      setTotal(data.total ?? (data.results || []).length)
    } catch (e) {
      setError(errorMessage(e, 'Search failed.'))
      setResults([])
    } finally {
      setTerm(q)
      setLoading(false)
    }
  }

  return (
    <div>
      <PageHeader title="Search Records"/>
      <Card>
        <div style={{ display: 'flex', gap: 8 }}>
          <SearchInput value={query} onChange={setQuery} onEnter={handleSearch}
            placeholder="Search by pupil name, LRN, subject, school year, or words on the scanned form..."/>
          <Btn variant="primary" onClick={handleSearch} disabled={loading || !query.trim()}>
            {loading ? 'Searching...' : 'Search'}
          </Btn>
        </div>
        <div className="filter-bar" style={{ margin: '10px 0 0' }}>
          <span className="text-muted" style={{ fontSize: 11 }}>Only in:</span>
          <FilterSelect value={filters.grade} onChange={v => setFilter('grade', v)} allLabel="All grades" options={withExtras(GRADE_LEVELS, options.grade_levels)}/>
          <FilterSelect value={filters.section} onChange={v => setFilter('section', v)} allLabel="All sections" options={options.sections}/>
          <FilterSelect value={filters.school_year} onChange={v => setFilter('school_year', v)} allLabel="All school years" options={options.school_years}/>
        </div>
      </Card>

      <StatusBanner error={error} onRetry={handleSearch}/>

      {results !== null && (
        <Card>
          <div className="hint" style={{ fontSize: 12, marginTop: 0, marginBottom: 10 }}>
            {total > results.length
              ? <>Showing the first <strong>{results.length}</strong> of <strong>{total.toLocaleString()}</strong> records that match <strong>"{term}"</strong>. Add words or use the filters to narrow it down.</>
              : <><strong>{results.length}</strong> result{results.length !== 1 ? 's' : ''} for <strong>"{term}"</strong></>}
          </div>
          {results.length === 0
            ? <EmptyState icon="🔍">No records found for "{term}".</EmptyState>
            : <ResultsTable results={results} term={term}/>}
        </Card>
      )}
    </div>
  )
}
