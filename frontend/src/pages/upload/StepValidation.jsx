import { useState } from 'react'
import { Card, Btn, Badge, Notice } from '../../components/ui/index'
import ScanPreview from '../../components/ui/ScanPreview'
import { NA, plural } from '../../utils/format'

// Flagged fields get a position-based key (_k), not f.field: names can repeat across
// year blocks on a Form 137, and keying by name would collapse them into one entry.
const flaggedFields = (scanResult) =>
  (scanResult?.fields || [])
    .map((f, i) => ({ ...f, _k: String(i) }))
    .filter(f => f.flagged || f.status === 'warn')

// Learning areas the OCR could not read ("Unread learning area Grade 2"), or read twice in one
// block ("English #2"): a person types what is printed on the form
const nameOf = (field) => field.slice(0, field.lastIndexOf(' '))
const needsName = (label) => label.startsWith('Unread learning area') || /\s#\d+$/.test(label)
const subjectsToName = (scanResult) =>
  [...new Set((scanResult?.fields || []).filter(f => f.field.includes(' ')).map(f => nameOf(f.field)).filter(needsName))]

function LearningAreaNames({ labels, names, onChange }) {
  if (labels.length === 0) return null
  return (
    <Card title="Learning area names" meta={`${labels.length} to check`}>
      <div className="hint" style={{ marginTop: 0 }}>
        These rows have no readable learning area, or the same one twice. Type the name printed on the form, or leave it as it is.
      </div>
      {labels.map(label => (
        <div key={label} className="btn-row" style={{ marginBottom: 6 }}>
          <span style={{ minWidth: 220 }}>{label}</span>
          <input className="fld" value={names[label] ?? ''} onChange={e => onChange(label, e.target.value)}
            placeholder="Learning area as printed" aria-label={`Name for ${label}`}/>
        </div>
      ))}
    </Card>
  )
}

function FlaggedFieldCard({ field: f, value, confirmed, onChange, onConfirm, onNA }) {
  return (
    <div className={`review-card${confirmed ? ' done' : ''}`}>
      <div className="review-card-hd">
        <strong>{f.field}</strong>
        <Badge type={confirmed ? 'b-green' : 'b-amber'}>{confirmed ? '✓ Confirmed' : f.conf > 0 ? `${f.conf}% conf` : 'Unreadable'}</Badge>
      </div>
      <div className="review-card-ocr">
        OCR read: <code className="inline-code mono">"{f.raw || f.value}"</code>
      </div>
      <div className="btn-row">
        <input
          className="fld review-input"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && onConfirm()}
          placeholder="Enter grade"
        />
        <Btn variant={confirmed ? 'secondary' : 'success'} size="sm" onClick={onConfirm}>{confirmed ? 'Edit' : 'Confirm'}</Btn>
        <Btn size="sm" onClick={onNA}>N/A</Btn>
        {confirmed && value && <span className="review-result">→ {value}</span>}
      </div>
    </div>
  )
}

export default function StepValidation({ data, onNext, onBack }) {
  // Computed once so the list never changes shape mid-review
  const [flagged]               = useState(() => flaggedFields(data.scanResult))
  const [values,    setValues]    = useState(() => Object.fromEntries(flagged.map(f => [f._k, ''])))
  const [confirmed, setConfirmed] = useState(() => Object.fromEntries(flagged.map(f => [f._k, false])))
  const [error,     setError]     = useState('')
  const [labels]                  = useState(() => subjectsToName(data.scanResult))
  const [names,     setNames]     = useState(data.renames || {})
  const renames = Object.fromEntries(Object.entries(names).map(([k, v]) => [k, v.trim()]).filter(([, v]) => v))
  const renameCard = <LearningAreaNames labels={labels} names={names} onChange={(label, v) => setNames(n => ({ ...n, [label]: v }))}/>

  const doneCount = Object.values(confirmed).filter(Boolean).length
  const remaining = flagged.length - doneCount

  const handleChange = (key, value) => {
    setValues(prev => ({ ...prev, [key]: value }))
    // Editing a confirmed value un-confirms it
    if (confirmed[key]) setConfirmed(prev => ({ ...prev, [key]: false }))
    setError('')
  }

  const handleConfirm = (f) => {
    if (!values[f._k]) {
      setError(`Please enter a value for "${f.field}" before confirming. Use "N/A" if the field is blank in the source.`)
      return
    }
    setConfirmed(prev => ({ ...prev, [f._k]: true }))
    setError('')
  }

  const handleNA = (key) => {
    setValues(prev => ({ ...prev, [key]: NA }))
    setConfirmed(prev => ({ ...prev, [key]: true }))
    setError('')
  }

  const handleSave = () => {
    const pending = flagged.filter(f => !confirmed[f._k])
    if (pending.length > 0) {
      setError(`${plural(pending.length, 'field')} still need review: ${pending.map(f => f.field).join(', ')}`)
      return
    }
    const corrections = flagged.map(f => ({ field: f.field, raw: f.raw, corrected_val: values[f._k] || NA }))
    onNext({ ...data, corrections, renames })
  }

  if (flagged.length === 0) {
    return (
      <div>
      {renameCard}
      <Card>
        <div className="empty-state" style={{ color: 'var(--green)' }}>
          <div className="empty-icon">✓</div>
          <strong>No flags — all fields auto-approved.</strong><br/>You can proceed directly to saving.
          <div style={{ marginTop: 16 }}>
            <Btn variant="primary" onClick={() => onNext({ ...data, corrections: [], renames })}>Proceed to confirm →</Btn>
          </div>
        </div>
      </Card>
      </div>
    )
  }

  return (
    <div>
      <div className="banner banner-warn">
        <span className="banner-icon">⚠</span>
        <div style={{ flex: 1 }}>
          <strong>{plural(flagged.length, 'field')} flagged</strong> for human review. Compare each value against the physical Form 137.
        </div>
        <Badge type={remaining === 0 ? 'b-green' : 'b-amber'}>{doneCount} / {flagged.length} reviewed</Badge>
      </div>

      <Notice>{error}</Notice>
      {renameCard}

      <div className="review-layout">
        {/* Left: source document stays in view while scrolling the list */}
        <div style={{ position: 'sticky', top: 0 }}>
          <Card title="Source document — compare against this">
            <ScanPreview file={data.file} alt="Source scan" className="review-source"/>
            <div className="hint" style={{ marginTop: 10, lineHeight: 1.6 }}>
              Type the correct grade, then click <strong>Confirm</strong> or press <strong>Enter</strong>.
              Click <strong>N/A</strong> if the field is blank in the source.
            </div>
          </Card>
        </div>

        {/* Right: scrollable list of flagged fields + progress footer */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="review-list">
            {flagged.map(f => (
              <FlaggedFieldCard
                key={f._k}
                field={f}
                value={values[f._k]}
                confirmed={confirmed[f._k]}
                onChange={v => handleChange(f._k, v)}
                onConfirm={() => handleConfirm(f)}
                onNA={() => handleNA(f._k)}
              />
            ))}
          </div>

          <div className="review-footer">
            <div className="review-dots">
              {flagged.map(f => (
                <div key={f._k} className={`review-dot${confirmed[f._k] ? ' done' : ''}`}
                  title={`${f.field}${confirmed[f._k] ? ` → ${values[f._k]}` : ' — pending'}`}/>
              ))}
              <span className="hint" style={{ margin: '0 0 0 4px' }}>{doneCount} of {flagged.length} confirmed</span>
            </div>
            <div className="btn-row">
              <Btn onClick={onBack}>← Back</Btn>
              <Btn variant="primary" onClick={handleSave} disabled={remaining > 0} style={{ flex: 1, justifyContent: 'center' }}>
                {remaining > 0 ? `${plural(remaining, 'field')} remaining — scroll up to review` : 'All confirmed — proceed to save →'}
              </Btn>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
