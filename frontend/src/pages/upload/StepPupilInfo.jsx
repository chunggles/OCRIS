import { useRef, useState } from 'react'
import { SCHOOL_YEARS, CURRENT_SCHOOL_YEAR } from '../../data/constants'
import { Card, Btn, FormGroup, Notice } from '../../components/ui/index'
import { useClassPicker, NO_CLASS } from '../../utils/useClassPicker'
import { isPdf } from '../../components/ui/ScanPreview'
import { useObjectUrl } from '../../utils/useObjectUrl'
import { formatMB, plural } from '../../utils/format'

const DEFAULT_CLASS = { grade: 'Grade 5', section: '', school_year: CURRENT_SCHOOL_YEAR }
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'application/pdf']
const MAX_BYTES = 20 * 1024 * 1024
const MAX_FORMS = 30

const SCAN_GUIDELINES = [
  ['green', 'Yes',  'Scan at 300 DPI minimum for accurate OCR'],
  ['green', 'Yes',  'Use grayscale or black and white mode'],
  ['green', 'Yes',  'Document completely flat — no folds or wrinkles'],
  ['green', 'Yes',  'All grade boxes fully visible inside the frame'],
  ['amber', 'Note', 'Handwritten grades will be flagged for review — this is normal'],
  ['amber', 'Note', 'Blank fields stored as N/A, never zero'],
  ['amber', 'Note', 'For a PDF, only the first page is read — one form per file'],
  ['rose',  'No',   'Phone camera photos — shadows distort OCR'],
  ['rose',  'No',   'Torn or severely water-damaged documents'],
]

// One row per chosen file: the scan plus the pupil it belongs to
let lastRowId = 0
const newRow = (file, pupil = {}) => ({ id: ++lastRowId, file, last_name: '', first_name: '', lrn: '', ...pupil })

const fileProblem = (file) => {
  if (!ACCEPTED_TYPES.includes(file.type)) return 'only JPG, PNG or PDF files are accepted'
  if (file.size > MAX_BYTES) return 'the file must be under 20 MB'
  return null
}

function validate(rows, classProblem) {
  if (classProblem) return classProblem
  if (rows.length === 0) return 'Please choose at least one scanned Form 137 file.'
  const unnamed = rows.filter(r => !r.last_name.trim() || !r.first_name.trim())
  if (unnamed.length) return `Please enter the pupil's name for: ${unnamed.map(r => r.file.name).join(', ')}.`
  return null
}

function DropZone({ onFiles }) {
  const inputRef = useRef(null)
  return (
    <div className="dropzone"
      onClick={() => inputRef.current?.click()}
      onDragOver={e => e.preventDefault()}
      onDrop={e => { e.preventDefault(); onFiles(e.dataTransfer.files) }}>
      {/* The value is cleared after each pick so the same file can be chosen again */}
      <input ref={inputRef} type="file" accept=".jpg,.jpeg,.png,.pdf" multiple hidden
        onChange={e => { onFiles(e.target.files); e.target.value = '' }}/>
      <div className="dropzone-icon">📁</div>
      <div className="dropzone-title" style={{ color: 'var(--blue)' }}>Click to browse or drag and drop</div>
      <div className="dropzone-sub">You can choose several forms at once — JPG, PNG or PDF — 300 DPI recommended — Max 20 MB each</div>
    </div>
  )
}

function FormRow({ row, number, onChange, onRemove }) {
  const preview = useObjectUrl(isPdf(row.file) ? null : row.file)
  return (
    <div className="queue-item">
      {preview ? <img src={preview} alt="" className="queue-thumb"/> : <div className="queue-thumb">{isPdf(row.file) && 'PDF'}</div>}
      <div className="queue-body">
        <div className="queue-file">
          <span><strong>{number}. {row.file.name}</strong> — {formatMB(row.file.size)}</span>
          <Btn size="sm" onClick={onRemove}>Remove</Btn>
        </div>
        <div className="form-row-3">
          <input className="fld" value={row.last_name} onChange={e => onChange('last_name', e.target.value)} placeholder="Last name *" aria-label={`Last name for ${row.file.name}`}/>
          <input className="fld" value={row.first_name} onChange={e => onChange('first_name', e.target.value)} placeholder="First name *" aria-label={`First name for ${row.file.name}`}/>
          <input className="fld" value={row.lrn} onChange={e => onChange('lrn', e.target.value)} placeholder="LRN (optional)" aria-label={`LRN for ${row.file.name}`}/>
        </div>
      </div>
    </div>
  )
}

// Step 1: pick the class once, then one or more scanned forms, each with its pupil's name.
// `initial.queue` restores what was entered when the user comes back to this step.
export default function StepPupilInfo({ initial = {}, onNext }) {
  const restored = initial.queue || []
  const [cls,   setCls]   = useState(() => {
    const form = restored[0]?.form
    return form ? { grade: form.grade, section: form.section, school_year: form.school_year } : DEFAULT_CLASS
  })
  const [rows,  setRows]  = useState(() => restored.map(({ file, form }) =>
    newRow(file, { last_name: form.last_name, first_name: form.first_name, lrn: form.lrn })))
  const [error, setError] = useState('')

  const picker = useClassPicker(cls.grade, cls.section)
  const { grade, section, sectionNames } = picker

  const setClass = (key, value) => setCls(c => ({ ...c, [key]: value }))
  // Sections belong to a grade level, so changing the grade clears the chosen section
  const handleGrade = (value) => setCls(c => ({ ...c, grade: value, section: '' }))

  const setRow    = (id, key, value) => setRows(list => list.map(r => (r.id === id ? { ...r, [key]: value } : r)))
  const removeRow = (id) => setRows(list => list.filter(r => r.id !== id))

  const handleFiles = (fileList) => {
    const accepted = [], problems = []
    for (const file of Array.from(fileList || [])) {
      const problem = fileProblem(file)
      if (problem) problems.push(`${file.name}: ${problem}.`)
      else accepted.push(file)
    }
    const room = MAX_FORMS - rows.length
    if (accepted.length > room) problems.push(`Only ${MAX_FORMS} forms can be uploaded at a time.`)
    setRows(list => [...list, ...accepted.slice(0, Math.max(room, 0)).map(file => newRow(file))])
    setError(problems.join(' '))
  }

  const handleNext = () => {
    const problem = validate(rows, picker.problem)
    if (problem) { setError(problem); return }
    setError('')
    onNext({
      queue: rows.map(r => ({
        file: r.file,
        form: {
          last_name: r.last_name.trim(), first_name: r.first_name.trim(), lrn: r.lrn.trim(),
          grade, section, school_year: cls.school_year,
        },
      })),
    })
  }

  return (
    <div className="g2">
      <div>
        <Card title="Class">
          {picker.locked && !section && <Notice>{NO_CLASS}</Notice>}
          <div className="form-row-3">
            <FormGroup label="Grade level">
              {picker.locked
                ? <select className="fld" value={grade} disabled><option>{grade}</option></select>
                : (
                  <select className="fld" value={grade} onChange={e => handleGrade(e.target.value)}>
                    {picker.gradeLevels.map(g => <option key={g}>{g}</option>)}
                  </select>
                )}
            </FormGroup>
            <FormGroup label="Section *">
              {picker.locked
                ? <select className="fld" value={section} disabled><option>{section}</option></select>
                : (
                  <select className="fld" value={section} onChange={e => setClass('section', e.target.value)} disabled={sectionNames.length === 0}>
                    <option value="">{picker.sectionPlaceholder}</option>
                    {sectionNames.map(s => <option key={s}>{s}</option>)}
                  </select>
                )}
            </FormGroup>
            <FormGroup label="School year">
              <select className="fld" value={cls.school_year} onChange={e => setClass('school_year', e.target.value)}>
                {SCHOOL_YEARS.map(y => <option key={y}>{y}</option>)}
              </select>
            </FormGroup>
          </div>
          <div className="hint">
            {picker.locked ? 'Your forms are filed under your assigned class.' : 'Every form you choose below is filed under this class.'}
          </div>
        </Card>

        <Card title={rows.length ? `Scanned forms (${rows.length})` : 'Scanned forms'}>
          <Notice>{error}</Notice>
          <DropZone onFiles={handleFiles}/>
          {rows.map((row, i) => (
            <FormRow key={row.id} row={row} number={i + 1}
              onChange={(key, value) => setRow(row.id, key, value)} onRemove={() => removeRow(row.id)}/>
          ))}
          <div className="btn-row" style={{ marginTop: 12 }}>
            <Btn variant="primary" onClick={handleNext}>
              {rows.length > 1 ? `Next: Check ${plural(rows.length, 'form')} →` : 'Next: Check image quality →'}
            </Btn>
            {rows.length > 0 && <Btn onClick={() => setRows([])}>Clear all</Btn>}
          </div>
          {rows.length > 1 && <div className="hint">The forms are read and checked one after another, in this order.</div>}
        </Card>
      </div>

      <Card title="Scan guidelines">
        {SCAN_GUIDELINES.map(([color, label, text]) => (
          <div key={text} className="guideline">
            <span className="guideline-tag" style={{ color: `var(--${color})` }}>{label}</span>
            <span>{text}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}
