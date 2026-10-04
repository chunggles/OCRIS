import { useEffect, useState } from 'react'
import { Card, Alert, Btn, ConfBar, StatusBanner } from '../../components/ui/index'
import { ocrAPI } from '../../utils/api'
import { useObjectUrl } from '../../utils/useObjectUrl'
import { errorMessage, formatMB } from '../../utils/format'
import { pupilName } from './shared'

const STATUS_STYLE = {
  good: { color: 'green', bar: 'cf-h', alert: 'green' },
  fair: { color: 'amber', bar: 'cf-m', alert: 'amber' },
  poor: { color: 'rose',  bar: 'cf-l', alert: 'rose' },
}

const VERDICT_TEXT = {
  good: 'This scan should read well.',
  fair: 'Usable, but some fields may need manual review.',
  poor: 'OCR is likely to misread this scan. Rescanning is recommended.',
}

// Checks the real image on the server (resolution, contrast, brightness, sharpness, tilt, ink coverage)
function useQualityCheck(file) {
  const [quality, setQuality] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true); setError(null)
    ocrAPI.checkQuality(file)
      .then(result => { if (!cancelled) setQuality(result) })
      .catch(e => { if (!cancelled) setError(errorMessage(e, 'Quality check failed.')) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [file])

  return { quality, loading, error }
}

function QualityReport({ quality }) {
  if (quality.error) return <Alert type="blue">{quality.error} OCR can still be run.</Alert>
  const verdict = STATUS_STYLE[quality.status]
  return (
    <>
      {quality.metrics.map(m => {
        const style = STATUS_STYLE[m.status]
        return (
          <div key={m.key} style={{ marginBottom: 10 }}>
            <div className="metric-row">
              <span>{m.label}</span><strong style={{ color: `var(--${style.color})` }}>{m.value}</strong>
            </div>
            <ConfBar pct={m.score} cls={style.bar}/>
            {m.tip && <div className="hint" style={{ marginTop: 3 }}>{m.tip}</div>}
          </div>
        )
      })}
      <Alert type={verdict.alert} style={{ marginBottom: 14 }}>
        <strong>{quality.assessment}.</strong> {VERDICT_TEXT[quality.status]}
      </Alert>
    </>
  )
}

export default function StepQuality({ data, onNext, onBack }) {
  const { file, form } = data
  const { quality, loading: checking, error: checkError } = useQualityCheck(file)
  const [running, setRunning] = useState(false)
  const [error,   setError]   = useState('')
  const preview = useObjectUrl(file)

  const handleRunOCR = async () => {
    setRunning(true); setError('')
    try {
      const scanResult = await ocrAPI.upload(file, {
        pupil_name:  pupilName(form),
        grade_level: form.grade,
        section:     form.section,
        school_year: form.school_year,
        lrn:         form.lrn,
      })
      onNext({ ...data, scanResult })
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Check that OCRIS is running and try again." : e?.data?.detail || 'Upload failed.')
    } finally {
      setRunning(false)
    }
  }

  const isPoor = quality?.status === 'poor'

  return (
    <div className="g2">
      <Card title="Document preview">
        {preview && <img src={preview} alt="Preview" className="upload-preview" style={{ maxHeight: 'none' }}/>}
        <div style={{ fontSize: 12 }}><strong>{file?.name}</strong> — {formatMB(file?.size)}</div>
        <div className="hint" style={{ marginTop: 4 }}>{pupilName(form)} — {form.grade}</div>
      </Card>

      <Card title="Image quality">
        {error && <Alert type="rose" style={{ marginBottom: 10 }}>{error}</Alert>}
        {checking
          ? <StatusBanner loading/>
          : checkError
            ? <StatusBanner error={checkError}/>
            : <QualityReport quality={quality}/>}
        <div className="btn-row">
          <Btn variant={isPoor ? 'secondary' : 'primary'} onClick={handleRunOCR} disabled={running || checking}>
            {running ? 'Running OCR...' : isPoor ? 'Run OCR anyway' : 'Run OCR →'}
          </Btn>
          <Btn variant={isPoor ? 'primary' : 'secondary'} onClick={onBack}>{isPoor ? '← Choose another scan' : 'Back'}</Btn>
        </div>
        {running && <div className="hint" style={{ marginTop: 10 }}>Reading the form — this can take up to a minute. Keep this page open.</div>}
      </Card>
    </div>
  )
}
