import { Card, Btn, Badge, ConfBar, Alert } from '../../components/ui/index'
import { isNA, NA } from '../../utils/format'
import { roughlyEqual } from '../../utils/compare'
import { pupilName, SummaryTiles } from './shared'

const listOf = (value) => (isNA(value) ? [] : value.split(',').map(v => v.trim()))

// Details typed on the upload form that disagree with what the scan says.
// Only compared when the scan has a value; small OCR slips are tolerated.
function detailMismatches(form, fields) {
  const read = Object.fromEntries(fields.map(f => [f.field, f.value]))
  const issues = []
  const scannedName = read['Pupil Name']
  if (!isNA(scannedName) && !roughlyEqual(scannedName, pupilName(form))) {
    issues.push(['Name', scannedName, pupilName(form)])
  }
  const years = listOf(read['School Year'])
  if (years.length && !years.includes(form.school_year)) {
    issues.push(['School year', years.join(', '), form.school_year])
  }
  const sections = listOf(read['Section'])
  if (sections.length && !sections.some(s => roughlyEqual(s, form.section, 0.8))) {
    issues.push(['Section', sections.join(', '), form.section])
  }
  // "Grade N" can be compared; secondary forms only give the year level ("Year I"), which can't
  const grades = listOf(read['Grade Level']).filter(g => g.startsWith('Grade'))
  if (grades.length && !grades.includes(form.grade)) {
    issues.push(['Grade level', grades.join(', '), form.grade])
  }
  return issues
}

function OcrField({ field: f }) {
  const isNull = f.status === 'null' || f.status === 'null-f'
  const status = isNull ? 'null' : f.status
  // Approval comes from the OCR's agreement check, so colour by status rather than raw confidence
  const badgeType = status === 'ok' ? 'b-green' : status === 'warn' ? 'b-amber' : 'b-grey'
  const badgeText = isNull ? 'Blank' : f.conf > 0 ? `${f.conf}%` : 'Unreadable'
  return (
    <div className={`ocr-field ${status}`}>
      <div className="ocr-lbl">{f.field}<Badge type={badgeType}>{badgeText}</Badge></div>
      <div className={`ocr-val${f.status === 'warn' ? ' flagged' : isNull ? ' null-v' : ''}`}>{f.value || f.raw || NA}</div>
      {f.status === 'warn' && <ConfBar pct={f.conf} cls="cf-l"/>}
    </div>
  )
}

export default function StepExtraction({ data, onNext, onBack }) {
  const { form, scanResult } = data
  const fields  = scanResult?.fields || []
  const summary = scanResult?.summary || {}
  const mismatches = detailMismatches(form, fields)

  return (
    <div>
      {mismatches.length > 0 && (
        <Alert type="amber">
          <strong>Check the pupil details.</strong> The scan doesn't match what was entered on the first step:
          <ul style={{ margin: '6px 0 0 18px' }}>
            {mismatches.map(([label, scanned, entered]) => (
              <li key={label}>{label}: scan shows <strong>{scanned}</strong>, entered <strong>{entered}</strong></li>
            ))}
          </ul>
          <div style={{ marginTop: 6 }}>If the entered details are wrong, go back to step 1. The saved record uses the entered details.</div>
        </Alert>
      )}
      <SummaryTiles tiles={[
        { value: summary.auto_approved,       label: 'Auto-approved',          color: 'green' },
        { value: summary.flagged,             label: 'Flagged — needs review', color: 'amber' },
        { value: summary.null_count,          label: 'Blank — stored as N/A',  color: 'grey' },
        { value: `${summary.overall_conf}%`,  label: 'Overall confidence',     color: 'blue' },
      ]}/>
      <Card title={`Extracted fields — ${pupilName(form)} / ${form.grade} / ${form.school_year}`}>
        <div className="ocr-grid" style={{ marginBottom: 14 }}>
          {fields.map((f, i) => <OcrField key={i} field={f}/>)}
        </div>
        <div className="btn-row">
          <Btn variant="primary" onClick={() => onNext()}>Proceed to validation →</Btn>
          <Btn onClick={onBack}>Back</Btn>
        </div>
      </Card>
    </div>
  )
}
