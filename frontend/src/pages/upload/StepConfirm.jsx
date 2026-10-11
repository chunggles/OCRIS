import { useState } from 'react'
import { Card, Alert, Btn, InfoRow } from '../../components/ui/index'
import { ocrAPI } from '../../utils/api'
import { pupilName, lrnProblem } from './shared'
import { isNA } from '../../utils/format'

function CorrectionSummary({ corrections, summary }) {
  return (
    <Card title="Correction summary">
      {corrections.length > 0
        ? corrections.map((c, i) => (
          <div key={i} className="diff-row">
            <div className="diff-lbl">{c.field}</div>
            <div className="diff-ocr">{c.raw || '?'}</div>
            <div className="diff-arr">→</div>
            <div className="diff-user">{c.corrected_val}</div>
          </div>
        ))
        : <div style={{ color: 'var(--green)', fontSize: 12, padding: '8px 0' }}>No corrections needed — all fields auto-approved.</div>}
      <div className="sep"/>
      <div className="text-muted" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
        <span>Auto-approved: <strong style={{ color: 'var(--green)' }}>{summary.auto_approved || 0}</strong></span>
        <span>Corrected: <strong style={{ color: 'var(--amber)' }}>{corrections.length}</strong></span>
        <span>N/A: <strong>{summary.null_count || 0}</strong></span>
      </div>
    </Card>
  )
}

export default function StepConfirm({ data, onSuccess, onBack }) {
  const { form, file, scanResult } = data
  const corrections = data.corrections || []
  // The name and LRN typed on the first step; when left blank, what was read from the form
  const readFrom = (label) => scanResult?.fields?.find(f => f.field === label)?.value
  const [name, setName] = useState(() => pupilName(form) || (isNA(readFrom('Pupil Name')) ? '' : readFrom('Pupil Name')))
  const [lrn,  setLrn]  = useState(() => form.lrn || (isNA(readFrom('LRN')) ? '' : readFrom('LRN')))
  const [agreed,  setAgreed]  = useState(false)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const handleSave = async () => {
    if (!name.trim()) { setError("Enter the pupil's name as it is written on the form."); return }
    const lrnError = lrnProblem(lrn.trim())
    if (lrnError) { setError(lrnError); return }
    if (!agreed) { setError('Please tick the confirmation checkbox before saving.'); return }
    setError(''); setLoading(true)
    try {
      onSuccess(await ocrAPI.validate({
        scan_id:     scanResult?.scan_id,
        pupil_name:  name.trim(),
        lrn:         lrn.replace(/[\s-]/g, ''),
        renames:     data.renames || {},
        grade_level: form.grade,
        section:     form.section,
        school_year: form.school_year,
        corrections: corrections.map(({ field, corrected_val }) => ({ field, corrected_val })),
        confirmed:   true,
      }))
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Save failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="g2">
      <CorrectionSummary corrections={corrections} summary={scanResult?.summary || {}}/>
      <Card title="Record summary">
        <InfoRow label="Pupil name"><input className="fld" value={name} onChange={e => setName(e.target.value)} placeholder="Last name, First name"/></InfoRow>
        <InfoRow label="Grade / Section">{form.grade} — {form.section}</InfoRow>
        <InfoRow label="School year">{form.school_year}</InfoRow>
        <InfoRow label="LRN"><input className="fld" value={lrn} onChange={e => setLrn(e.target.value)} placeholder="12 digits (optional)" inputMode="numeric" maxLength={14}/></InfoRow>
        <InfoRow label="File">{file?.name}</InfoRow>
        <InfoRow label="Scan ID"><span className="mono-sm">{scanResult?.scan_id}</span></InfoRow>
        <div className="sep"/>
        {error && <Alert type="rose" style={{ marginBottom: 10 }}>{error}</Alert>}
        <Alert type="blue" style={{ marginBottom: 14, fontSize: 11 }}>
          <label className="confirm-check">
            <input type="checkbox" checked={agreed} onChange={e => setAgreed(e.target.checked)}/>
            <span>I have checked all flagged fields against the physical Form 137.</span>
          </label>
        </Alert>
        <div className="btn-row">
          <Btn variant="success" onClick={handleSave} disabled={loading} style={{ flex: 1, justifyContent: 'center' }}>
            {loading ? 'Saving...' : 'Save record'}
          </Btn>
          <Btn onClick={onBack}>Back and edit</Btn>
        </div>
      </Card>
    </div>
  )
}
