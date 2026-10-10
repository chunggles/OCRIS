import { useCallback, useState } from 'react'
import { useApp } from '../context/AppContext'
import { ROLES } from '../data/constants'
import { Btn, Notice, PageHeader, StatusBanner } from '../components/ui/index'
import { recordsAPI, sectionsAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { NO_CLASS } from '../utils/useClassPicker'
import { Sheet, sheetOf, blankSheet, recordOf, setIn } from './form137/sheet'

const sameClass = (user, record) => record.grade_level === user.assigned_grade
  && record.section.toLowerCase() === (user.assigned_section || '').toLowerCase()

// The sheet with its buttons. Remounted by the page to start a fresh form or open another record.
// With `record` it edits that saved record; otherwise the first save creates one, and later saves update it.
function Form137({ record, tree, onNew }) {
  const { nav, user } = useApp()
  const [sheet,     setSheet]     = useState(() => (record ? sheetOf(record) : blankSheet()))
  const [saving,    setSaving]    = useState(false)
  const [saved,     setSaved]     = useState(record || null)  // the record as last saved
  const [justSaved, setJustSaved] = useState(false)
  const [error,     setError]     = useState('')

  // Whether the sheet differs from what was last saved
  const snapshot = JSON.stringify(sheet)
  const [cleanSnapshot, setCleanSnapshot] = useState(snapshot)
  const dirty = snapshot !== cleanSnapshot

  const update = (path, value) => setSheet(s => setIn(s, path, value))

  const handleNew = () => {
    if (dirty && !window.confirm(saved ? 'Leave this form? Changes since the last save will be lost.' : 'Clear everything typed on this form?')) return
    onNew()
  }

  const handleSave = async () => {
    const [body, problem] = recordOf(sheet)
    if (problem) { setError(problem); return }
    // A teacher only sees their own class, so the record must be filed under it
    if (user?.role === ROLES.TEACHER) {
      if (!user.assigned_grade || !user.assigned_section) { setError(NO_CLASS); return }
      if (!sameClass(user, body)) {
        setError(`You can only file forms under your class, ${user.assigned_grade} – ${user.assigned_section}. `
          + `The last block with grades on this form is ${body.grade_level} – ${body.section}.`)
        return
      }
    }
    setError(''); setSaving(true)
    try {
      setSaved(saved ? await recordsAPI.update(saved.record_id, body) : await recordsAPI.create(body))
      setCleanSnapshot(snapshot); setJustSaved(true)
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Save failed.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="no-print">
        <div className="btn-row" style={{ marginBottom: 12 }}>
          <Btn variant="success" onClick={handleSave} disabled={saving || (Boolean(saved) && !dirty)}>
            {saving ? 'Saving...' : saved ? 'Save changes' : 'Save record'}
          </Btn>
          {saved && <Btn variant="primary" onClick={() => nav('detail', { recordId: saved.record_id })} disabled={dirty}>View record</Btn>}
          <Btn onClick={() => window.print()}>Print</Btn>
          <Btn onClick={handleNew}>{saved ? 'Fill out another form' : 'Clear form'}</Btn>
        </div>
        <Notice type="error">{error}</Notice>
        <Notice type="success">
          {justSaved && !dirty && `Saved as ${saved.record_id}, filed under ${saved.grade_level} – ${saved.section}. General average ${saved.general_average}, ${saved.remarks}.`}
        </Notice>
        <div className="hint" style={{ marginTop: 0, marginBottom: 12 }}>
          {saved
            ? `Editing record ${saved.record_id}. Change anything on the form, then click Save changes.`
            : 'Type on the form as you would write on paper. Leave a box empty if it is blank. The final rating fills itself in from the four quarters unless you type one. Print on long bond paper (8.5 × 13 in).'}
        </div>
      </div>

      {/* the sheet keeps its paper proportions; on a narrow screen it scrolls sideways */}
      <div className="sheet-scroll"><Sheet sheet={sheet} update={update} tree={tree}/></div>
    </div>
  )
}

// Opened from the menu it is a blank form; nav('fillform', { recordId }) opens that record for editing
export default function FillFormPage() {
  const { nav, navParams } = useApp()
  const recordId = navParams?.recordId
  const [formNo, setFormNo] = useState(1)

  const fetchRecord = useCallback(() => (recordId ? recordsAPI.get(recordId) : Promise.resolve(null)), [recordId])
  const { data: record, loading, error, refetch } = useFetch(fetchRecord)
  const fetchTree = useCallback(() => sectionsAPI.tree(), [])
  const { data: tree } = useFetch(fetchTree)

  // A fresh sheet; nav() without a record also drops the one being edited
  const startNew = () => { nav('fillform'); setFormNo(n => n + 1) }

  const header = <div className="no-print"><PageHeader title={recordId ? 'Edit Form 137 (SF10-ES)' : 'Fill Out Form 137 (SF10-ES)'}/></div>
  // `record` can lag one render behind `recordId`, so wait until the two agree
  if (recordId && (loading || error || record?.record_id !== recordId)) {
    return (
      <div>
        {header}
        {error ? <StatusBanner error={error} onRetry={refetch}/> : <StatusBanner loading/>}
        {error && <Btn onClick={startNew}>Start a blank form</Btn>}
      </div>
    )
  }
  return (
    <div>
      {header}
      <Form137 key={`${recordId || 'new'}-${formNo}`} record={recordId ? record : null} tree={tree} onNew={startNew}/>
    </div>
  )
}
