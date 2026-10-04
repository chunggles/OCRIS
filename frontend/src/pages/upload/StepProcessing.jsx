import { Card, Btn } from '../../components/ui/index'
import { SummaryTiles } from './shared'

export default function StepProcessing({ data, onNext }) {
  const { scanResult } = data
  const summary = scanResult?.summary || {}

  return (
    <div style={{ maxWidth: 560 }}>
      <Card title="OCR complete">
        <SummaryTiles size="lg" tiles={[
          { value: summary.auto_approved, label: 'Auto-approved', color: 'green' },
          { value: summary.flagged,       label: 'Flagged',       color: 'amber' },
          { value: summary.null_count,    label: 'N/A (blank)',   color: 'grey' },
        ]}/>
        <div className="success-box">
          ✓ Form read successfully. Scan ID: <strong className="mono">{scanResult?.scan_id}</strong>
        </div>
        <Btn variant="primary" onClick={onNext} style={{ width: '100%', justifyContent: 'center' }}>View extraction results →</Btn>
      </Card>
    </div>
  )
}
