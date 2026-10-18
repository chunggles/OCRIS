// The on-screen SF10-ES (Learner Permanent Academic Record for Elementary School, formerly
// Form 137), laid out like the printed two-page form: the front (learner details, eligibility and
// four year blocks) and the back (four more year blocks and the certification boxes). Used to fill
// out and edit records (FillFormPage) and, read-only, to print a typed-in record (PrintFormBtn).
//
// Learning areas are not pre-printed; each is typed in by hand. Ratings are given per term (three
// a year), as on the SF10-ES (Revised 2025), or per quarter (four) for a record kept in quarters,
// such as an older form typed in; `sheet.grading_period` says which. Both are saved under the
// keys Q1-Q4 (Q4 blank for terms) so records and the API keep one shape.
//
// The printed sheet is also meant to be scanned back in, so the layout keeps what the OCR
// relies on (backend/api/ocr/table.py): two ruled grade tables side by side with a clear strip
// between them, the wording of the labels, and one grade per ruled cell.
import sealUrl from '../../assets/deped-seal.png'
import logoUrl from '../../assets/deped-logo.png'
import { GRADE_LEVELS, GRADING_PERIODS, SCHOOL_YEARS } from '../../data/constants'
import { sectionsOf } from '../../utils/api'
import { gradingPeriodOf, isNA, PASSING_GRADE } from '../../utils/format'

const ALL_KEYS = ['Q1', 'Q2', 'Q3', 'Q4', 'final']   // every grade a row can hold, whichever the grading period
const periodsOf = (sheet) => GRADING_PERIODS[sheet.grading_period].keys   // its terms or quarters
const FRONT_BLOCKS = 4  // year blocks on the front; the back holds as many more
const BLOCK_COUNT = FRONT_BLOCKS * 2
const AREA_ROWS = 15  // rows of each grade table above "General Average"
const REMEDIAL_ROWS = 2
const CERTIFICATION_COUNT = 3
const BLOCK_TEXT_FIELDS = ['school', 'school_id', 'district', 'division', 'region', 'grade_level', 'section', 'school_year', 'adviser']

const BLANK_LEARNER = { last_name: '', first_name: '', name_ext: '', middle_name: '', lrn: '', birthdate: '', sex: '' }
const BLANK_ELIGIBILITY = {
  kinder_progress_report: false, eccd_checklist: false, school_name: '', school_id: '', school_address: '',
  pept_rating: '', exam_date: '', others: '', testing_center: '', remark: '',
}

const BLANK_CERTIFICATION = {
  learner_name: '', lrn: '', grade: '', school_name: '', school_id: '', division: '', last_school_year: '', date: '', signatory: '',
}

const areaRow = (subject, id) => ({ id, subject, Q1: '', Q2: '', Q3: '', Q4: '', final: '' })

function blankBlock() {
  return {
    ...Object.fromEntries(BLOCK_TEXT_FIELDS.map(key => [key, ''])),
    rows: Array.from({ length: AREA_ROWS }, (_, id) => areaRow('', id)),
    remedial: {
      from: '', to: '',
      rows: Array.from({ length: REMEDIAL_ROWS }, () => ({ area: '', final: '', mark: '', recomputed: '', remarks: '' })),
    },
  }
}

export const blankSheet = (gradingPeriod = 'term') => ({
  grading_period: gradingPeriod,
  learner: BLANK_LEARNER,
  eligibility: BLANK_ELIGIBILITY,
  blocks: Array.from({ length: BLOCK_COUNT }, blankBlock),
  certifications: Array.from({ length: CERTIFICATION_COUNT }, () => BLANK_CERTIFICATION),
  total_pages: '',
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

// The final rating is the rounded mean of the terms or quarters (`periods`), unless one is typed in
const computedFinal = (row, periods) => (periods.every(t => !isBlank(row[t]) && !isBadGrade(row[t]))
  ? String(Math.round(periods.reduce((sum, t) => sum + Number(row[t]), 0) / periods.length))
  : '')
const finalOf = (row, periods) => String(row.final).trim() || computedFinal(row, periods)
const remarkOf = (row, periods) => {
  const final = finalOf(row, periods)
  if (!final || isBadGrade(final)) return ''
  return Number(final) >= PASSING_GRADE ? 'PASSED' : 'FAILED'
}
const hasGrades = (row) => ALL_KEYS.some(key => !isBlank(row[key]))
const blockHasGrades = (block) => block.rows.some(hasGrades)

function generalAverage(block, periods) {
  const finals = block.rows.filter(r => !isBlank(r.subject)).map(r => finalOf(r, periods)).filter(f => f && !isBadGrade(f)).map(Number)
  return finals.length ? (finals.reduce((a, b) => a + b, 0) / finals.length).toFixed(1) : ''
}

// "GMRC (Good Manners and Right Conduct)" → "GMRC", "*Arabic Language" → "Arabic Language":
// the short name is what a scanned form is saved under, so both kinds of record line up
const subjectName = (text) => text.replace(/^\*/, '').replace(/\s*\(.*\)\s*$/, '').trim()

// (grades for the API, problem message) for one block. Rows with neither a subject nor grades are left out.
function gradesOf(block, blockNo, periods) {
  const grades = {}
  for (const [i, row] of block.rows.entries()) {
    const subject = subjectName(row.subject)
    if (!hasGrades(row)) continue
    if (!subject) return [null, `Block ${blockNo}: type the learning area for row ${i + 1}.`]
    if (grades[subject]) return [null, `Block ${blockNo}: ${subject} is listed twice.`]
    if ([...periods, 'final'].some(key => isBadGrade(row[key]))) return [null, `Block ${blockNo}, ${subject}: grades must be numbers from 0 to 100.`]
    grades[subject] = { ...Object.fromEntries(periods.map(t => [t, String(row[t] ?? '').trim()])), final: finalOf(row, periods) }
  }
  return [grades, null]
}

// Whether any Q4 grade is typed on the sheet, which switching to terms would remove
export const hasQ4Grades = (sheet) => sheet.blocks.some(block => block.rows.some(row => !isBlank(row.Q4)))

// The sheet kept in `period` ('term' or 'quarter'); terms have no Q4, so it is cleared
export const withGradingPeriod = (sheet, period) => ({
  ...sheet,
  grading_period: period,
  blocks: period === 'term' ? sheet.blocks.map(block => ({ ...block, rows: block.rows.map(row => ({ ...row, Q4: '' })) })) : sheet.blocks,
})

// ── Saving and restoring ─────────────────────────────────────────────────────

// (record for the API, problem message). One sheet is saved as one record. The record's own class
// and grades are those of the last block that has grades, which is the learner's latest school
// year on the form; every block is kept under `details`, so the sheet comes back as it was typed.
export function recordOf(sheet) {
  const { learner } = sheet
  if (isBlank(learner.last_name) || isBlank(learner.first_name)) return [null, "Please enter the learner's last name and first name."]
  const filled = sheet.blocks.map((block, i) => [block, i + 1]).filter(([block]) => blockHasGrades(block))
  if (filled.length === 0) return [null, 'Enter the grades for at least one learning area.']
  const periods = periodsOf(sheet)
  let latest = null
  for (const [block, blockNo] of filled) {
    if (!block.grade_level || !block.section || !block.school_year) {
      return [null, `Block ${blockNo} has grades: choose its grade, section and school year.`]
    }
    const [grades, problem] = gradesOf(block, blockNo, periods)
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
    grading_period: sheet.grading_period,
    details: {
      name_ext: learner.name_ext.trim(), middle_name: learner.middle_name.trim(),
      birthdate: learner.birthdate.trim(), sex: learner.sex.trim(),
      eligibility: sheet.eligibility,
      blocks: sheet.blocks,
      certifications: sheet.certifications,
      total_pages: sheet.total_pages.trim(),
    },
  }, null]
}

// A block as saved, topped up with any field a newer version of the form has added
function restoredBlock(saved) {
  const blank = blankBlock()
  const rows = Array.isArray(saved?.rows) && saved.rows.length ? saved.rows : blank.rows
  return {
    ...blank, ...saved,
    rows: rows.slice(0, AREA_ROWS).map((row, id) => ({ ...areaRow('', id), ...row, id })),
    remedial: { ...blank.remedial, ...saved?.remedial, rows: blank.remedial.rows.map((row, i) => ({ ...row, ...saved?.remedial?.rows?.[i] })) },
  }
}

// A record that was not typed on this sheet (or predates it): its grades go in the block for its grade level
function blocksFromGrades(record) {
  const gradeNo = Number((record.grade_level || '').replace(/\D/g, '')) || 1
  const index = Math.min(Math.max(gradeNo, 1), BLOCK_COUNT) - 1
  return Array.from({ length: BLOCK_COUNT }, (_, i) => {
    const block = blankBlock()
    if (i !== index) return block
    const subjects = Object.entries(record.grades || {}).slice(0, AREA_ROWS)
    const rows = [...subjects, ...Array(AREA_ROWS - subjects.length).fill(['', {}])].map(([subject, g], id) => ({
      ...areaRow(subject, id), ...Object.fromEntries(ALL_KEYS.map(key => [key, isNA(g[key]) ? '' : String(g[key])])),
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
    grading_period: gradingPeriodOf(record),
    learner: {
      ...BLANK_LEARNER,
      last_name: last.trim(), first_name: given.join(',').trim(), lrn: record.lrn || '',
      name_ext: details.name_ext || '', middle_name: details.middle_name || '',
      birthdate: details.birthdate || details.birth_date || '', sex: details.sex || '',
    },
    eligibility: { ...BLANK_ELIGIBILITY, ...details.eligibility },
    // a record saved before the back page was added has fewer blocks; the rest start blank
    blocks: Array.isArray(details.blocks) && details.blocks.length
      ? Array.from({ length: BLOCK_COUNT }, (_, i) => (details.blocks[i] ? restoredBlock(details.blocks[i]) : blankBlock()))
      : blocksFromGrades(record),
    certifications: Array.from({ length: CERTIFICATION_COUNT }, (_, i) => ({ ...BLANK_CERTIFICATION, ...details.certifications?.[i] })),
    total_pages: details.total_pages || '',
  }
}

// ── The sheet ────────────────────────────────────────────────────────────────

const GRADE_COLUMN_WIDTHS = {
  term:    ['46%', '8%', '8%', '8%', '11.5%', '18.5%'],
  quarter: ['40%', '7%', '7%', '7%', '7%', '11.5%', '20.5%'],
}
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
  const periods = periodsOf(sheet)
  const quarterly = sheet.grading_period === 'quarter'
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
          <Columns widths={GRADE_COLUMN_WIDTHS[sheet.grading_period]}/>
          <thead>
            <tr>
              <th rowSpan="2">{i % 2 ? 'Learning Areas' : 'LEARNING AREAS'}</th>
              <th colSpan={periods.length}>{quarterly ? 'Quarterly Rating' : 'Term Rating'}</th>
              <th rowSpan="2">Final Rating</th>
              <th rowSpan="2">Remarks</th>
            </tr>
            <tr>{periods.map((t, n) => <th key={t}>{n + 1}</th>)}</tr>
          </thead>
          <tbody>
            {b.rows.map((row, r) => (
              <tr key={row.id}>
                <td>{cell([...path, 'rows', r, 'subject'], { left: true, 'aria-label': 'Learning area' })}</td>
                {[...periods, 'final'].map((key, n) => (
                  <td key={key}>
                    {cell([...path, 'rows', r, key], {
                      bad: isBadGrade(row[key]), inputMode: 'decimal', maxLength: 5,
                      placeholder: key === 'final' ? computedFinal(row, periods) : undefined,
                      'aria-label': `${row.subject || 'Learning area'} ${key === 'final' ? 'final rating' : `${quarterly ? 'quarter' : 'term'} ${n + 1}`}`,
                    })}
                  </td>
                ))}
                <td className="sf-auto">{remarkOf(row, periods)}</td>
              </tr>
            ))}
            <tr>
              <td className="sf-label">General Average</td>
              {periods.map(t => <td key={t}/>)}
              <td className="sf-auto">{generalAverage(b, periods)}</td>
              <td/>
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
                  <b>{i < FRONT_BLOCKS ? 'Conducted from:' : 'Date Conducted:'}</b> {blank([...path, 'remedial', 'from'], { flex: 1, center: true })}
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

  const certification = (c, i) => {
    const path = ['certifications', i]
    return (
      <div className="sf-cert" key={i}>
        <div className="sf-band">CERTIFICATION</div>
        <div className="sf-box">
          <div className="sf-line">
            <b>I CERTIFY</b> that this is a true record of {blank([...path, 'learner_name'], { flex: 4 })}
            with LRN {blank([...path, 'lrn'], { flex: 2, inputMode: 'numeric', maxLength: 12 })}
            and that he/she is eligible for admission to Grade {blank([...path, 'grade'], { width: '3em', center: true })}.
          </div>
          <div className="sf-line">
            <b>School Name</b> {blank([...path, 'school_name'], { flex: 4 })}
            <b>School ID</b> {blank([...path, 'school_id'], { width: '7em' })}
            <b>Division</b> {blank([...path, 'division'], { flex: 2 })}
            <b>Last School Year Attended:</b> {blank([...path, 'last_school_year'], { width: '8em', center: true })}
          </div>
          <div className="sf-line sf-sign">
            <div className="sf-sign-col" style={{ flex: 2 }}>{blank([...path, 'date'], { center: true })}<span>Date</span></div>
            <div className="sf-sign-col" style={{ flex: 4 }}>{blank([...path, 'signatory'], { center: true })}<span>Signature of Principal/School Head over Printed Name</span></div>
            <i className="sf-seal-note">(Affix School Seal here)</i>
          </div>
        </div>
      </div>
    )
  }

  return (
    <>
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
        <div className="sf-pair">{sheet.blocks.slice(2, FRONT_BLOCKS).map((b, i) => block(b, i + 2))}</div>
        <div className="sf-revised">Revised 2025 based on DepEd Order No. 10, s. 2024</div>
      </div>

      <div className="sf10 sf-back">
        <div className="sf-pagehead">
          <b>SF10-ES</b>
          <span>Page 2 of {blank(['total_pages'], { width: '3em', center: true, maxLength: 3, 'aria-label': 'Total pages' })}</span>
        </div>
        <div className="sf-band">SCHOLASTIC RECORD</div>
        <div className="sf-pair">{sheet.blocks.slice(FRONT_BLOCKS, FRONT_BLOCKS + 2).map((b, i) => block(b, i + FRONT_BLOCKS))}</div>
        <div className="sf-pair">{sheet.blocks.slice(FRONT_BLOCKS + 2).map((b, i) => block(b, i + FRONT_BLOCKS + 2))}</div>

        <div className="sf-foronly"><b>For Transfer Out /Elementary School Completer Only</b></div>
        {sheet.certifications.map(certification)}
        <div className="sf-revised sf-back-foot"><span>May add Certification Box if needed</span>Revised 2025 based on DepEd Order No. 10, s. 2024</div>
      </div>
    </>
  )
}
