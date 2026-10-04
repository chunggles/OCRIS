import { Card, Btn, InfoRow, RemarksBadge } from '../../components/ui/index'
import { pupilName } from './shared'

export default function StepSuccess({ data, result, onNav }) {
  const { form } = data
  return (
    <Card>
      <div className="success-wrap">
        <div className="success-ring">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 28, height: 28 }}>
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </div>
        <div className="success-title">Record saved</div>
        <div className="success-sub">{pupilName(form)} — {form.grade} — AY {form.school_year}</div>
        <div className="success-details">
          <InfoRow label="Record ID"><span className="mono-sm">{result?.record_id || '—'}</span></InfoRow>
          <InfoRow label="General average"><strong>{result?.general_average || '—'}</strong></InfoRow>
          <InfoRow label="Remarks"><RemarksBadge remarks={result?.remarks}/></InfoRow>
        </div>
        <div className="btn-row">
          <Btn variant="primary" onClick={() => onNav('upload')}>Upload another Form 137</Btn>
          <Btn onClick={() => onNav('records')}>View all records</Btn>
          <Btn onClick={() => onNav('analytics')}>View analytics</Btn>
        </div>
      </div>
    </Card>
  )
}
