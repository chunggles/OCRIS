// The on-screen SF10-ES (Learner Permanent Academic Record for Elementary School, formerly
// Form 137), laid out like the printed front page. Used to fill out and edit records
// (FillFormPage) and, read-only, to print a typed-in record (PrintFormBtn).
//
// The printed sheet is also meant to be scanned back in, so the layout keeps what the OCR
// relies on (backend/api/ocr/table.py): two ruled grade tables side by side with a clear strip
// between them, the wording of the labels, and one grade per ruled cell.
import sealUrl from '../../assets/deped-seal.png'
import logoUrl from '../../assets/deped-logo.png'
import { GRADE_LEVELS, SCHOOL_YEARS } from '../../data/constants'
import { sectionsOf } from '../../utils/api'
import { isNA, PASSING_GRADE } from '../../utils/format'

const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4']
const GRADE_KEYS = [...QUARTERS, 'final']
const GMRC = 'GMRC (Good Manners and Right Conduct)'
// Learning areas pre-printed in each of the four year blocks (top left, top right, bottom left, bottom right)
const PRINTED_AREAS = [
  ['Language', 'Reading and Literacy', 'Mathematics', GMRC, 'Makabansa'],
  ['Filipino', 'English', 'Mathematics', GMRC, 'Makabansa'],
  ['Filipino', 'English', 'Mathematics', 'Science', GMRC, 'Makabansa'],
  ['Filipino', 'English', 'Mathematics', 'Science', GMRC, 'Araling Panlipunan', 'EPP', 'MAPEH', 'Music & Arts', 'Physical Education & Health'],
]
const LAST_AREAS = ['*Arabic Language', '*Islamic Values Education']
const AREA_ROWS = 15  // rows of each grade table above "General Average"
// Printed down the Remarks column of the first three blocks on this edition of the form
const OLD_CURRICULUM = [true, true, true, false]
const REMEDIAL_ROWS = 2
const BLOCK_TEXT_FIELDS = ['school', 'school_id', 'district', 'division', 'region', 'grade_level', 'section', 'school_year', 'adviser']

const BLANK_LEARNER = { last_name: '', first_name: '', name_ext: '', middle_name: '', lrn: '', birthdate: '', sex: '' }
const BLANK_ELIGIBILITY = {
  kinder_progress_report: false, eccd_checklist: false, school_name: '', school_id: '', school_address: '',
  pept_rating: '', exam_date: '', others: '', testing_center: '', remark: '',
}

const areaRow = (subject, id) => ({ id, subject, Q1: '', Q2: '', Q3: '', Q4: '', final: '' })

function blankBlock(index) {
  const printed = PRINTED_AREAS[index]
  const areas = [...printed, ...Array(AREA_ROWS - printed.length - LAST_AREAS.length).fill(''), ...LAST_AREAS]
  return {
    ...Object.fromEntries(BLOCK_TEXT_FIELDS.map(key => [key, ''])),
    rows: areas.map(areaRow),
    remedial: {
      from: '', to: '',
      rows: Array.from({ length: REMEDIAL_ROWS }, () => ({ area: '', final: '', mark: '', recomputed: '', remarks: '' })),
    },
  }
}

export const blankSheet = () => ({
  learner: BLANK_LEARNER,
  eligibility: BLANK_ELIGIBILITY,
  blocks: PRINTED_AREAS.map((_, i) => blankBlock(i)),
})

// Copy of `object` with the value at `path` (keys and array indexes) replaced
export function setIn(object, [key, ...rest], value) {
  const next = rest.length ? setIn(object[key], rest, value) : value
  return Array.isArray(object) ? object.map((item, i) => (i === key ? next : item)) : { ...object, [key]: next }
}
const getIn = (object, path) => path.reduce((value, key) => value?.[key], object)

// ── Grades ───────────────────────────────────────────────────────────────────

const isBlank = (v) => String(v ?? '').trim() === ''
const isBadGrade = (v) => !isBlank(v) && !(Number(v) >= 0 && Number(v) <= 100)

// The final rating is the rounded mean of the four quarters, unless one is typed in
const computedFinal = (row) => (QUARTERS.every(q => !isBlank(row[q]) && !isBadGrade(row[q]))
  ? String(Math.round(QUARTERS.reduce((sum, q) => sum + Number(row[q]), 0) / QUARTERS.length))
  : '')
const finalOf = (row) => String(row.final).trim() || computedFinal(row)
const remarkOf = (row) => {
  const final = finalOf(row)
  if (!final || isBadGrade(final)) return ''
  return Number(final) >= PASSING_GRADE ? 'PASSED' : 'FAILED'
}
const hasGrades = (row) => GRADE_KEYS.some(key => !isBlank(row[key]))
const blockHasGrades = (block) => block.rows.some(hasGrades)

function generalAverage(block) {
  const finals = block.rows.filter(r => !isBlank(r.subject)).map(finalOf).filter(f => f && !isBadGrade(f)).map(Number)
  return finals.length ? (finals.reduce((a, b) => a + b, 0) / finals.length).toFixed(1) : ''
}

// "GMRC (Good Manners and Right Conduct)" → "GMRC", "*Arabic Language" → "Arabic Language":
// the short name is what a scanned form is saved under, so both kinds of record line up
const subjectName = (text) => text.replace(/^\*/, '').replace(/\s*\(.*\)\s*$/, '').trim()

// (grades for the API, problem message) for one block. Rows with neither a subject nor grades are left out.
function gradesOf(block, blockNo) {
  const grades = {}
  for (const [i, row] of block.rows.entries()) {
    const subject = subjectName(row.subject)
    if (!hasGrades(row)) continue
    if (!subject) return [null, `Block ${blockNo}: type the learning area for row ${i + 1}.`]
    if (grades[subject]) return [null, `Block ${blockNo}: ${subject} is listed twice.`]
    if (GRADE_KEYS.some(key => isBadGrade(row[key]))) return [null, `Block ${blockNo}, ${subject}: grades must be numbers from 0 to 100.`]
    grades[subject] = { ...Object.fromEntries(QUARTERS.map(q => [q, String(row[q]).trim()])), final: finalOf(row) }
  }
  return [grades, null]
}

// ── Saving and restoring ─────────────────────────────────────────────────────

// (record for the API, problem message). One sheet is saved as one record. The record's own class
// and grades are those of the last block that has grades, which is the learner's latest school
// year on the form; every block is kept under `details`, so the sheet comes back as it was typed.
export function recordOf(sheet) {
  const { learner } = sheet
  if (isBlank(learner.last_name) || isBlank(learner.first_name)) return [null, "Please enter the learner's last name and first name."]
  const filled = sheet.blocks.map((block, i) => [block, i + 1]).filter(([block]) => blockHasGrades(block))
  if (filled.length === 0) return [null, 'Enter the grades for at least one learning area.']
  let latest = null
  for (const [block, blockNo] of filled) {
    if (!block.grade_level || !block.section || !block.school_year) {
      return [null, `Block ${blockNo} has grades: choose its grade, section and school year.`]
    }
    const [grades, problem] = gradesOf(block, blockNo)
    if (problem) return [null, problem]
    latest = { block, grades }
  }
  return [{
    pupil_name:    `${learner.last_name.trim()}, ${learner.first_name.trim()}`,
    lrn:           learner.lrn.trim(),
    grade_level:   latest.block.grade_level,
    section:       latest.block.section,
    school_year:   latest.block.school_year,
    class_adviser: latest.block.adviser.trim(),
    grades:        latest.grades,
    details: {
      name_ext: learner.name_ext.trim(), middle_name: learner.middle_name.trim(),
      birthdate: learner.birthdate.trim(), sex: learner.sex.trim(),
      eligibility: sheet.eligibility,
      blocks: sheet.blocks,
    },
  }, null]
}

// A block as saved, topped up with any field a newer version of the form has added
function restoredBlock(saved, index) {
  const blank = blankBlock(index)
  const rows = Array.isArray(saved?.rows) && saved.rows.length ? saved.rows : blank.rows
  return {
    ...blank, ...saved,
    rows: rows.slice(0, AREA_ROWS).map((row, id) => ({ ...areaRow('', id), ...row, id })),
    remedial: { ...blank.remedial, ...saved?.remedial, rows: blank.remedial.rows.map((row, i) => ({ ...row, ...saved?.remedial?.rows?.[i] })) },
  }
}

// A record that was not typed on this sheet (or predates it): its grades go in the block for its grade level
function blocksFromGrades(record) {
  const gradeNo = Number((record.grade_level || '').replace(/\D/g, '')) || PRINTED_AREAS.length
  const index = Math.min(Math.max(gradeNo, 1), PRINTED_AREAS.length) - 1
  return PRINTED_AREAS.map((_, i) => {
    const block = blankBlock(i)
    if (i !== index) return block
    const subjects = Object.entries(record.grades || {}).slice(0, AREA_ROWS)
    const rows = [...subjects, ...Array(AREA_ROWS - subjects.length).fill(['', {}])].map(([subject, g], id) => ({
      ...areaRow(subject, id), ...Object.fromEntries(GRADE_KEYS.map(key => [key, isNA(g[key]) ? '' : String(g[key])])),
    }))
    return {
      ...block, rows,
      grade_level: record.grade_level || '', section: record.section || '', school_year: record.school_year || '',
      adviser: record.class_adviser || '',
    }
  })
}

// What is written on the sheet for a saved record, so it can be edited or printed
export function sheetOf(record) {
  const details = record.details || {}
  const [last = '', ...given] = (record.pupil_name || '').split(',')
  return {
    learner: {
      ...BLANK_LEARNER,
      last_name: last.trim(), first_name: given.join(',').trim(), lrn: record.lrn || '',
      name_ext: details.name_ext || '', middle_name: details.middle_name || '',
      birthdate: details.birthdate || details.birth_date || '', sex: details.sex || '',
    },
    eligibility: { ...BLANK_ELIGIBILITY, ...details.eligibility },
    blocks: Array.isArray(details.blocks) && details.blocks.length === PRINTED_AREAS.length
      ? details.blocks.map(restoredBlock)
      : blocksFromGrades(record),
  }
}

// ── The sheet ────────────────────────────────────────────────────────────────

const GRADE_COLUMN_WIDTHS = ['48%', '6.3%', '6.3%', '6.3%', '6.3%', '11%', '15.8%']
const REMEDIAL_COLUMN_WIDTHS = ['28.7%', '19.3%', '18.9%', '17.3%', '15.8%']
const REMEDIAL_COLUMNS = [['area', 'Learning Areas'], ['final', 'Final Rating'], ['mark', 'Remedial Class Mark'], ['recomputed', 'Recomputed Final Grade'], ['remarks', 'Remarks']]
const gradeNumber = (gradeLevel) => gradeLevel.replace(/\D/g, '')

function Columns({ widths }) {
  return <colgroup>{widths.map((width, i) => <col key={i} style={{ width }}/>)}</colgroup>
}

// `sheet` is what is written on the form (see blankSheet); `update(path, value)` changes one value
// of it; `tree` is the section tree, for the section choices. With `readOnly` nothing can be
// typed, which is how a saved record is shown for printing.
export function Sheet({ sheet, update = () => {}, tree, readOnly = false }) {
  // An underlined blank bound to one value of the sheet
  const blank = (path, { flex, width, center, ...rest } = {}) => (
    <input className={`sf-in${center ? ' center' : ''}`} style={{ flex, width }} value={getIn(sheet, path) ?? ''}
      onChange={e => update(path, e.target.value)} readOnly={readOnly} {...rest}/>
  )
  // A cell of a ruled table bound to one value of the sheet
  const cell = (path, { bad, left, ...rest } = {}) => (
    <input className={`sf-cell${bad ? ' bad' : ''}${left ? ' left' : ''}`} value={getIn(sheet, path) ?? ''}
      onChange={e => update(path, e.target.value)} readOnly={readOnly} {...rest}/>
  )
  const tick = (key, label) => (
    <label className="sf-tick">
      <input type="checkbox" checked={Boolean(sheet.eligibility[key])} disabled={readOnly}
        onChange={e => update(['eligibility', key], e.target.checked)}/>
      <i>{label}</i>
    </label>
  )

  // A dropdown on screen; on a read-only sheet, the chosen value written on the blank
  const choice = (value, onChange, options, { flex, width, label }) => (readOnly
    ? <span className="sf-in sf-static center" style={{ flex, width }}>{options.find(o => o.value === value)?.label ?? value}</span>
    : (
      <select className="sf-in center" style={{ flex, width }} value={value} onChange={e => onChange(e.target.value)} aria-label={label}>
        <option value=""/>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    ))

  const block = (b, i) => {
    const path = ['blocks', i]
    const sections = sectionsOf(tree, b.grade_level).map(s => s.name)
    // A section saved on the form stays selectable even if it has since left the Sections list
    const sectionOptions = [...new Set([...sections, b.section].filter(Boolean))].map(s => ({ value: s, label: s }))
    return (
      <div className="sf-block" key={i}>
        <div className="sf-class">
          <div className="sf-line">School: {blank([...path, 'school'], { flex: 5 })} School ID: {blank([...path, 'school_id'], { width: '6em' })}</div>
          <div className="sf-line">
            District: {blank([...path, 'district'], { flex: 2 })} Division: {blank([...path, 'division'], { flex: 4 })}
            Region: {blank([...path, 'region'], { width: '4em' })}
          </div>
          <div className="sf-line">
            Classified as Grade:
            {choice(b.grade_level, v => update(path, { ...b, grade_level: v, section: '' }),
              GRADE_LEVELS.map(g => ({ value: g, label: gradeNumber(g) })), { width: '3em', label: `Block ${i + 1} grade` })}
            Section: {choice(b.section, v => update([...path, 'section'], v), sectionOptions, { flex: 3, label: `Block ${i + 1} section` })}
            School Year: {choice(b.school_year, v => update([...path, 'school_year'], v),
              SCHOOL_YEARS.map(y => ({ value: y, label: y })), { width: '7.5em', label: `Block ${i + 1} school year` })}
          </div>
          <div className="sf-line">
            Name of Adviser/Teacher: {blank([...path, 'adviser'], { flex: 3 })} Signature: <span className="sf-in sf-static" style={{ flex: 2 }}/>
          </div>
        </div>

        <table className="sf-table">
          <Columns widths={GRADE_COLUMN_WIDTHS}/>
          <thead>
            <tr>
              <th rowSpan="2">{i % 2 ? 'Learning Areas' : 'LEARNING AREAS'}</th>
              <th colSpan="4">Quarterly Rating</th>
              <th rowSpan="2">Final Rating</th>
              <th rowSpan="2">Remarks</th>
            </tr>
            <tr>{QUARTERS.map((q, n) => <th key={q}>{n + 1}</th>)}</tr>
          </thead>
          <tbody>
            {b.rows.map((row, r) => (
              <tr key={row.id}>
                <td>{cell([...path, 'rows', r, 'subject'], { left: true, 'aria-label': 'Learning area' })}</td>
                {GRADE_KEYS.map((key, n) => (
                  <td key={key}>
                    {cell([...path, 'rows', r, key], {
                      bad: isBadGrade(row[key]), inputMode: 'decimal', maxLength: 5,
                      placeholder: key === 'final' ? computedFinal(row) : undefined,
                      'aria-label': `${row.subject || 'Learning area'} ${key === 'final' ? 'final rating' : `quarter ${n + 1}`}`,
                    })}
                  </td>
                ))}
                {OLD_CURRICULUM[i]
                  ? r === 0 && (
                    <td rowSpan={AREA_ROWS + 1} className="sf-note">
                      <div><b>UNDER OLD CURRICULUM</b><br/><i>See attached old School Form 10 with learning areas<br/>based on DepEd Order No. 21, s. 2019</i></div>
                    </td>
                  )
                  : <td className="sf-auto">{remarkOf(row)}</td>}
              </tr>
            ))}
            <tr>
              <td className="sf-label">General Average</td>
              <td/><td/><td/><td/>
              <td className="sf-auto">{generalAverage(b)}</td>
              {!OLD_CURRICULUM[i] && <td/>}
            </tr>
          </tbody>
        </table>

        <table className="sf-table sf-remedial">
          <Columns widths={REMEDIAL_COLUMN_WIDTHS}/>
          <tbody>
            <tr>
              <th>Remedial Classes</th>
              <td colSpan="4">
                <div className="sf-line sf-conducted">
                  <b>Conducted from:</b> {blank([...path, 'remedial', 'from'], { flex: 1, center: true })}
                  <b>to</b> {blank([...path, 'remedial', 'to'], { flex: 1, center: true })}
                </div>
              </td>
            </tr>
            <tr>{REMEDIAL_COLUMNS.map(([, label]) => <th key={label}>{label}</th>)}</tr>
            {b.remedial.rows.map((_, r) => (
              <tr key={r}>
                {REMEDIAL_COLUMNS.map(([key, label]) => (
                  <td key={key}>{cell([...path, 'remedial', 'rows', r, key], { left: key === 'area', 'aria-label': `Remedial ${label}` })}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="sf10">
      <div className="sf-head">
        <div className="sf-formno">SF10-ES</div>
        <img src={sealUrl} alt="" className="sf-seal"/>
        <div className="sf-titles">
          <div>Republic of the Philippines</div>
          <div>Department of Education</div>
          <div className="sf-title">Learner Permanent Academic Record for Elementary School (SF10-ES)</div>
          <div className="sf-formerly">(Formerly Form 137)</div>
        </div>
        <img src={logoUrl} alt="" className="sf-logo"/>
      </div>

      <div className="sf-band">LEARNER'S PERSONAL INFORMATION</div>
      <div className="sf-line">
        LAST NAME: {blank(['learner', 'last_name'], { flex: 4, 'aria-label': 'Last name' })}
        FIRST NAME: {blank(['learner', 'first_name'], { flex: 4, 'aria-label': 'First name' })}
        NAME EXTN. (Jr,I,II) {blank(['learner', 'name_ext'], { width: '4.5em', 'aria-label': 'Name extension' })}
        MIDDLE NAME: {blank(['learner', 'middle_name'], { flex: 3, 'aria-label': 'Middle name' })}
      </div>
      <div className="sf-line">
        Learner Reference Number (LRN): {blank(['learner', 'lrn'], { flex: 3, inputMode: 'numeric', maxLength: 12, 'aria-label': 'LRN' })}
        Birthdate (mm/dd/yyyy): {blank(['learner', 'birthdate'], { flex: 4, placeholder: readOnly ? undefined : 'mm/dd/yyyy', 'aria-label': 'Birthdate' })}
        Sex: {blank(['learner', 'sex'], { width: '9em', 'aria-label': 'Sex' })}
      </div>

      <div className="sf-band sf-band-lg">ELIGIBILITY FOR ELEMENTARY SCHOOL ENROLLMENT</div>
      <div className="sf-box">
        <div className="sf-line">
          <i>Credential Presented for Grade 1:</i>
          <span style={{ flex: 1 }}/>{tick('kinder_progress_report', 'Kinder Progress Report')}
          <span style={{ flex: 1 }}/>{tick('eccd_checklist', 'ECCD Checklist')}<span style={{ flex: 3 }}/>
        </div>
        <div className="sf-line">
          Name of School: {blank(['eligibility', 'school_name'], { flex: 4 })}
          School ID: {blank(['eligibility', 'school_id'], { width: '7em' })}
          Address of School: {blank(['eligibility', 'school_address'], { flex: 5 })}
        </div>
      </div>
      <div className="sf-line">Other Credential Presented</div>
      <div className="sf-line sf-indent">
        PEPT Passer &nbsp;Rating: {blank(['eligibility', 'pept_rating'], { width: '5em' })}
        <span style={{ flex: 1 }}/>Date of Examination/Assessment (mm/dd/yyyy): {blank(['eligibility', 'exam_date'], { width: '10em' })}
        <span style={{ flex: 1 }}/>Others (Pls. Specify): {blank(['eligibility', 'others'], { width: '14em' })}
      </div>
      <div className="sf-line sf-indent">
        Name and Address of Testing Center: {blank(['eligibility', 'testing_center'], { flex: 4 })}
        Remark: {blank(['eligibility', 'remark'], { flex: 3 })}
      </div>

      <div className="sf-band">SCHOLASTIC RECORD</div>
      <div className="sf-pair">{sheet.blocks.slice(0, 2).map((b, i) => block(b, i))}</div>
      <div className="sf-pair">{sheet.blocks.slice(2, 4).map((b, i) => block(b, i + 2))}</div>
      <div className="sf-revised">Revised 2025 based on DepEd Order No. 10, s. 2024</div>
    </div>
  )
}
