import { useState } from 'react'
import { useApp } from '../context/AppContext'
import { Card, Btn, StatusBanner, EmptyState, PageHeader, RemarksBadge, SearchInput } from '../components/ui/index'
import { recordsAPI } from '../utils/api'
import { errorMessage, escapeRegExp, isNA } from '../utils/format'

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
        <tr><th>Pupil name</th><th>LRN</th><th>Grade</th><th>Section</th><th>SY</th><th>General avg</th><th>Remarks</th><th>Action</th></tr>
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
              <td><Btn size="sm" onClick={() => nav('detail', { recordId: r.record_id })} disabled={!r.record_id}>View</Btn></td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export default function SearchPage() {
  const [query,   setQuery]   = useState('')
  const [term,    setTerm]    = useState('') // the query the current results are for
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const handleSearch = async () => {
    const q = query.trim()
    if (!q) return
    setLoading(true); setError(null)
    try {
      const data = await recordsAPI.search(q)
      setResults(data.results || [])
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
            placeholder="Search by pupil name, LRN, grade level, or section..."/>
          <Btn variant="primary" onClick={handleSearch} disabled={loading || !query.trim()}>
            {loading ? 'Searching...' : 'Search'}
          </Btn>
        </div>
      </Card>

      <StatusBanner error={error} onRetry={handleSearch}/>

      {results !== null && (
        <Card>
          <div className="hint" style={{ fontSize: 12, marginTop: 0, marginBottom: 10 }}>
            <strong>{results.length}</strong> result{results.length !== 1 ? 's' : ''} for <strong>"{term}"</strong>
          </div>
          {results.length === 0
            ? <EmptyState icon="🔍">No records found for "{term}".</EmptyState>
            : <ResultsTable results={results} term={term}/>}
        </Card>
      )}
    </div>
  )
}
