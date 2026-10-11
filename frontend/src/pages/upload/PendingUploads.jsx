import { useEffect, useState } from 'react'
import { Card, Btn, Alert } from '../../components/ui/index'
import { ocrAPI } from '../../utils/api'
import { errorMessage, formatDateTime } from '../../utils/format'

// "Last, First" as stored on the scan, back into the two boxes of the upload form
const nameParts = (full = '') => {
  const [last = '', ...rest] = full.split(',')
  return { last_name: last.trim(), first_name: rest.join(',').trim() }
}

// Forms that were read but not saved, for example because the page was refreshed or the browser
// closed. They are kept on the server for a few days, and can be picked up from the extraction
// step. A batch's other forms were never uploaded, so those have to be chosen again.
export default function PendingUploads({ onResume }) {
  const [scans,   setScans]   = useState([])
  const [opening, setOpening] = useState('')
  const [error,   setError]   = useState('')

  useEffect(() => {
    let cancelled = false
    ocrAPI.pending().then(r => { if (!cancelled) setScans(r.results) }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  const open = async (scan) => {
    setOpening(scan.scan_id); setError('')
    try {
      const detail = await ocrAPI.scan(scan.scan_id)
      // The scan itself is shown beside the grades; without it the form can still be finished
      const blob = await ocrAPI.scanBlob(scan.scan_id).catch(() => null)
      const file = blob && new File([blob], detail.original_name || 'form', { type: blob.type })
      onResume({
        file,
        form: { ...nameParts(detail.pupil_name), lrn: detail.lrn || '', grade: detail.grade_level, section: detail.section, school_year: detail.school_year },
        scanResult: { scan_id: detail.scan_id, fields: detail.ocr_fields, summary: detail.summary, notes: detail.notes },
      })
    } catch (e) {
      const message = errorMessage(e, 'Could not open this upload.')
      setError(message === 'offline' ? "Can't reach the server. Try again in a moment." : message)
      setOpening('')
    }
  }

  if (scans.length === 0) return null
  return (
    <Card title={`Unfinished uploads (${scans.length})`}>
      <Alert type="amber">
        These forms were read but never saved. Carry on where you stopped, or ignore them: unsaved uploads are removed from the server after a few days.
      </Alert>
      {error && <Alert type="rose">{error}</Alert>}
      {scans.map(scan => (
        <div key={scan.scan_id} className="queue-item">
          <div className="queue-body">
            <div className="queue-file">{scan.original_name || scan.scan_id}</div>
            <div className="hint">
              {[scan.pupil_name, scan.grade_level, scan.section, `uploaded ${formatDateTime(scan.created_at)}`].filter(Boolean).join(' — ')}
            </div>
          </div>
          <Btn size="sm" variant="primary" disabled={Boolean(opening)} onClick={() => open(scan)}>
            {opening === scan.scan_id ? 'Opening…' : 'Continue'}
          </Btn>
        </div>
      ))}
    </Card>
  )
}
