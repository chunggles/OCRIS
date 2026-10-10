import { useCallback, useState } from 'react'
import { useApp } from '../context/AppContext'
import { isStaffRole } from '../data/constants'
import { Card, Btn, InfoRow, StatusBanner, EmptyState, PageHeader, RemarksBadge, Notice } from '../components/ui/index'
import DownloadScanBtn from '../components/ui/DownloadScanBtn'
import PrintFormBtn from './form137/PrintFormBtn'
import { recordsAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { formatDateTime, isNA, plural, NA, PASSING_GRADE, FOR_VERIFICATION } from '../utils/format'

const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4']
const GRADE_KEYS = [...QUARTERS, 'final']
// Pupil details an OIC or Admin can correct: [record field, label]
const EDITABLE_INFO = [
  ['pupil_name', 'Pupil name'], ['lrn', 'LRN'], ['grade_level', 'Grade level'],
  ['section', 'Section'], ['school_year', 'School year'],
]

// With `onChange`, every grade becomes an input (edit mode)
function GradesTable({ grades, onChange }) {
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
                {onChange ? GRADE_KEYS.map(key => (
                  <td key={key} className="center">
                    <input className="fld" style={{ width: 64, textAlign: 'center' }} value={isNA(g[key]) ? '' : g[key]}
                      placeholder={NA} onChange={e => onChange(subject, key, e.target.value)}/>
                  </td>
                )) : (
                  <>
                    {QUARTERS.map(q => (
                      <td key={q} className="center" style={{ color: isNA(g[q]) ? 'var(--text-3)' : 'var(--text)' }}>
                        {isNA(g[q]) ? NA : g[q]}
                      </td>
                    ))}
                    <td className="center" style={{ fontWeight: 700, color: isNA(g.final) ? 'var(--text-3)' : failing ? 'var(--rose)' : 'var(--text)' }}>
                      {isNA(g.final) ? NA : g.final}
                    </td>
                  </>
                )}
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

// What a typed-in SF10-ES holds beside the record's own grades; scanned records have none
const DETAIL_LABELS = [['middle_name', 'Middle name'], ['name_ext', 'Name extension'], ['birthdate', 'Birthdate'], ['sex', 'Sex']]

function FormDetailsCard({ record }) {
  const details = record.details || {}
  const info = DETAIL_LABELS.filter(([field]) => details[field])
  // Year blocks of the sheet other than the one this record is filed under
  const otherYears = (Array.isArray(details.blocks) ? details.blocks : [])
    .filter(b => b?.grade_level && !(b.grade_level === record.grade_level && b.school_year === record.school_year))
    .map(b => `${b.grade_level}${b.section ? ` – ${b.section}` : ''}${b.school_year ? ` (${b.school_year})` : ''}`)
  if (info.length === 0 && otherYears.length === 0) return null
  return (
    <Card title="Form 137 (SF10-ES) details">
      {info.map(([field, label]) => <InfoRow key={field} label={label}>{details[field]}</InfoRow>)}
      {otherYears.length > 0 && <InfoRow label="Other school years">{otherYears.join(' · ')}</InfoRow>}
      {otherYears.length > 0 && (
        <div className="hint">The grades above are for {record.grade_level}, {record.school_year}. Open the form to see the other school years.</div>
      )}
    </Card>
  )
}

export default function RecordDetailPage() {
  const { nav, navParams, user } = useApp()
  const recordId = navParams?.recordId

  const fetchRecord = useCallback(() => (recordId ? recordsAPI.get(recordId) : Promise.resolve(null)), [recordId])
  const { data: r, loading, error, refetch } = useFetch(fetchRecord)

  // `draft` holds the values being edited; null when not editing
  const [draft,     setDraft]     = useState(null)
  const [saving,    setSaving]    = useState(false)
  const [saveError, setSaveError] = useState('')

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

  const editing = draft !== null
  const grades = editing ? draft.grades : r.grades || {}
  const subjectCount = Object.keys(grades).length
  // a subject with nothing at all filled in was not taken; a subject with some grades but not others has gaps
  const missingCount = Object.values(grades).reduce((count, g) => {
    const blanks = GRADE_KEYS.filter(key => isNA(g?.[key])).length
    return count + (blanks < GRADE_KEYS.length ? blanks : 0)
  }, 0)

  const startEdit = () => {
    setSaveError('')
    setDraft({
      ...Object.fromEntries(EDITABLE_INFO.map(([field]) => [field, r[field] || ''])),
      grades: JSON.parse(JSON.stringify(r.grades || {})),
    })
  }
  const setInfo  = (field, value) => setDraft(d => ({ ...d, [field]: value }))
  const setGrade = (subject, key, value) =>
    setDraft(d => ({ ...d, grades: { ...d.grades, [subject]: { ...d.grades[subject], [key]: value } } }))

  const handleSave = async () => {
    setSaving(true); setSaveError('')
    try {
      await recordsAPI.update(recordId, draft)
      setDraft(null)
      refetch()
    } catch (e) {
      setSaveError(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Save failed.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      {header}
      <div className="btn-row" style={{ marginBottom: 12 }}>
        {backButton}
        {!editing && <PrintFormBtn record={r} size="" label={r.scan_id ? 'Print scanned form' : 'Print Form 137'}/>}
        <DownloadScanBtn scanId={r.scan_id} size="" variant="primary" label="Download original form"/>
        {/* A typed-in form has no scan; it is edited on the Form 137 sheet, by staff or by the class's teacher */}
        {!r.scan_id && !editing && <Btn variant="primary" onClick={() => nav('fillform', { recordId })}>Edit on Form 137</Btn>}
        {isStaffRole(user?.role) && !editing && <Btn onClick={startEdit}>Edit record</Btn>}
        {editing && <Btn variant="success" onClick={handleSave} disabled={saving}>{saving ? 'Saving...' : 'Save changes'}</Btn>}
        {editing && <Btn onClick={() => setDraft(null)} disabled={saving}>Cancel</Btn>}
      </div>
      <Notice type="error">{saveError}</Notice>
      {editing && (
        <div className="hint" style={{ marginTop: 0, marginBottom: 12 }}>
          Leave a grade empty if it is blank on the form. The general average and remarks are recalculated when you save.
        </div>
      )}

      <div className="grid-auto">
        <Card title="Pupil information">
          {editing
            ? EDITABLE_INFO.map(([field, label]) => (
              <InfoRow key={field} label={label}>
                <input className="fld" value={draft[field]} onChange={e => setInfo(field, e.target.value)}/>
              </InfoRow>
            ))
            : (
              <>
                <InfoRow label="Pupil name">{r.pupil_name || '—'}</InfoRow>
                <InfoRow label="LRN"><span className="mono">{r.lrn || '—'}</span></InfoRow>
                <InfoRow label="Grade level">{r.grade_level || '—'}</InfoRow>
                <InfoRow label="Section">{r.section || '—'}</InfoRow>
                <InfoRow label="School year">{r.school_year || '—'}</InfoRow>
              </>
            )}
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
        {!editing && missingCount > 0 && (
          <Notice type="error">
            {plural(missingCount, 'grade')} on this record {missingCount === 1 ? 'is' : 'are'} missing: <strong>{FOR_VERIFICATION}</strong>.
            Check {missingCount === 1 ? 'it' : 'them'} against the paper form. No value is estimated.
          </Notice>
        )}
        <GradesTable grades={grades} onChange={editing ? setGrade : undefined}/>
      </Card>

      <FormDetailsCard record={r}/>
      <CorrectionsCard corrections={r.corrections}/>
    </div>
  )
}
