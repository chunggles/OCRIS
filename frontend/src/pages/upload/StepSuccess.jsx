import { Card, Btn, InfoRow, RemarksBadge } from '../../components/ui/index'
import { plural } from '../../utils/format'
import { pupilName } from './shared'

// `position` of `total` is this form's place in the batch; `remaining` forms are still to be done
export default function StepSuccess({ data, result, position = 1, total = 1, remaining = 0, onNextForm, onNav }) {
  const { form } = data
  return (
    <Card>
      <div className="success-wrap">
        <div className="success-ring">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 28, height: 28 }}>
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </div>
        <div className="success-title">{total > 1 ? `Record saved — form ${position} of ${total}` : 'Record saved'}</div>
        <div className="success-sub">{pupilName(form)} — {form.grade} — AY {form.school_year}</div>
        <div className="success-details">
          <InfoRow label="Record ID"><span className="mono-sm">{result?.record_id || '—'}</span></InfoRow>
          <InfoRow label="General average"><strong>{result?.general_average || '—'}</strong></InfoRow>
          <InfoRow label="Remarks"><RemarksBadge remarks={result?.remarks}/></InfoRow>
        </div>
        {remaining > 0 ? (
          <>
            <div className="btn-row">
              <Btn variant="primary" onClick={onNextForm}>Next form ({position + 1} of {total}) →</Btn>
              <Btn onClick={() => onNav('records')}>Stop and view records</Btn>
            </div>
            <div className="hint">{plural(remaining, 'form')} left. Stopping here leaves {remaining === 1 ? 'it' : 'them'} unsaved.</div>
          </>
        ) : (
          <div className="btn-row">
            <Btn variant="primary" onClick={() => onNav('upload')}>Upload another Form 137</Btn>
            <Btn onClick={() => onNav('records')}>View all records</Btn>
            <Btn onClick={() => onNav('analytics')}>View analytics</Btn>
          </div>
        )}
      </div>
    </Card>
  )
}
