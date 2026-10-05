import { useRef, useState } from 'react'
import { GRADE_LEVELS, SCHOOL_YEARS, CURRENT_SCHOOL_YEAR } from '../../data/constants'
import { Card, Btn, FormGroup, Notice } from '../../components/ui/index'
import { useObjectUrl } from '../../utils/useObjectUrl'
import { formatMB } from '../../utils/format'

const DEFAULT_FORM = { last_name: '', first_name: '', grade: 'Grade 5', section: '', school_year: CURRENT_SCHOOL_YEAR, lrn: '' }
// PDFs can't be read by the OCR engine, so only images are accepted
const ACCEPTED_TYPES = ['image/jpeg', 'image/png']
const MAX_BYTES = 20 * 1024 * 1024

const SCAN_GUIDELINES = [
  ['green', 'Yes',  'Scan at 300 DPI minimum for accurate OCR'],
  ['green', 'Yes',  'Use grayscale or black and white mode'],
  ['green', 'Yes',  'Document completely flat — no folds or wrinkles'],
  ['green', 'Yes',  'All grade boxes fully visible inside the frame'],
  ['amber', 'Note', 'Handwritten grades will be flagged for review — this is normal'],
  ['amber', 'Note', 'Blank fields stored as N/A, never zero'],
  ['rose',  'No',   'Phone camera photos — shadows distort OCR'],
  ['rose',  'No',   'Torn or severely water-damaged documents'],
]

function validate(form, file) {
  if (!form.last_name || !form.first_name) return "Please enter the pupil's name."
  if (!form.section.trim()) return 'Please enter a section.'
  if (!file) return 'Please choose a scanned Form 137 file.'
  return null
}

function DropZone({ file, onFile }) {
  const inputRef = useRef(null)
  return (
    <div className={`dropzone${file ? ' has-file' : ''}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={e => e.preventDefault()}
      onDrop={e => { e.preventDefault(); onFile(e.dataTransfer.files[0]) }}>
      <input ref={inputRef} type="file" accept=".jpg,.jpeg,.png" hidden onChange={e => onFile(e.target.files[0])}/>
      {file ? (
        <>
          <div className="dropzone-icon">📄</div>
          <div className="dropzone-title" style={{ color: 'var(--green)' }}>{file.name}</div>
          <div className="dropzone-sub">{formatMB(file.size)} — click to change</div>
        </>
      ) : (
        <>
          <div className="dropzone-icon">📁</div>
          <div className="dropzone-title" style={{ color: 'var(--blue)' }}>Click to browse or drag and drop</div>
          <div className="dropzone-sub">JPG or PNG — 300 DPI recommended — Max 20 MB</div>
        </>
      )}
    </div>
  )
}

// `initial` restores what was entered when the user comes back to this step
export default function StepPupilInfo({ initial = {}, onNext }) {
  const [form,  setForm]  = useState(initial.form || DEFAULT_FORM)
  const [file,  setFile]  = useState(initial.file || null)
  const [error, setError] = useState('')
  const preview = useObjectUrl(file)

  const set = (key, value) => setForm(f => ({ ...f, [key]: value }))

  const handleFile = (f) => {
    if (!f) return
    if (!ACCEPTED_TYPES.includes(f.type)) { setError('Only JPG or PNG images are accepted. If your scan is a PDF, export it as an image first.'); return }
    if (f.size > MAX_BYTES) { setError('File must be under 20 MB.'); return }
    setError(''); setFile(f)
  }

  const handleNext = () => {
    const problem = validate(form, file)
    if (problem) { setError(problem); return }
    setError('')
    onNext({ file, form: { ...form, section: form.section.trim() } })
  }

  return (
    <div className="g2">
      <div>
        <Card title="Pupil information">
          <div className="form-row-2">
            <FormGroup label="Last name *">
              <input className="fld" value={form.last_name} onChange={e => set('last_name', e.target.value)} placeholder="e.g. Santos"/>
            </FormGroup>
            <FormGroup label="First name *">
              <input className="fld" value={form.first_name} onChange={e => set('first_name', e.target.value)} placeholder="e.g. Maria Joy L."/>
            </FormGroup>
          </div>
          <div className="form-row-3">
            <FormGroup label="Grade level">
              <select className="fld" value={form.grade} onChange={e => set('grade', e.target.value)}>
                {GRADE_LEVELS.map(g => <option key={g}>{g}</option>)}
              </select>
            </FormGroup>
            <FormGroup label="Section *">
              <input className="fld" value={form.section} onChange={e => set('section', e.target.value)} placeholder="e.g. Sampaguita"/>
            </FormGroup>
            <FormGroup label="School year">
              <select className="fld" value={form.school_year} onChange={e => set('school_year', e.target.value)}>
                {SCHOOL_YEARS.map(y => <option key={y}>{y}</option>)}
              </select>
            </FormGroup>
          </div>
          <FormGroup label="LRN (optional)">
            <input className="fld" value={form.lrn} onChange={e => set('lrn', e.target.value)} placeholder="12-digit Learner Reference Number"/>
          </FormGroup>
        </Card>

        <Card title="Upload scanned document">
          <Notice>{error}</Notice>
          <DropZone file={file} onFile={handleFile}/>
          {preview && <img src={preview} alt="Preview" className="upload-preview"/>}
          <div className="btn-row">
            <Btn variant="primary" onClick={handleNext}>Next: Check image quality →</Btn>
            {file && <Btn onClick={() => setFile(null)}>Clear</Btn>}
          </div>
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
