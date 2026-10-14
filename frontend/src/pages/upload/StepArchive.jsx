import { useState } from 'react'
import { Card, Alert, Btn } from '../../components/ui/index'
import ScanPreview from '../../components/ui/ScanPreview'
import { ocrAPI } from '../../utils/api'
import { formatMB } from '../../utils/format'
import { pupilName } from './shared'

// Archive-only forms skip quality check, OCR and grade review: the file is stored with its pupil's details
export default function StepArchive({ data, onSuccess, onBack }) {
  const { file, form } = data
  const [saving, setSaving] = useState(false)
  const [error,  setError]  = useState('')

  const handleSave = async () => {
    setSaving(true); setError('')
    try {
      onSuccess(await ocrAPI.upload(file, {
        pupil_name:   pupilName(form),
        grade_level:  form.grade,
        section:      form.section,
        school_year:  form.school_year,
        lrn:          form.lrn,
        archive_only: 'true',
      }))
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Check that OCRIS is running and try again." : e?.data?.detail || 'Upload failed.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="g2">
      <Card title="Document preview">
        <ScanPreview file={file} alt="Preview" className="upload-preview" style={{ maxHeight: 'none' }}/>
        <div style={{ fontSize: 12 }}><strong>{file?.name}</strong> — {formatMB(file?.size)}</div>
      </Card>
      <Card title="Archive form">
        {error && <Alert type="rose" style={{ marginBottom: 10 }}>{error}</Alert>}
        <Alert type="blue" style={{ marginBottom: 14 }}>
          This form will be stored for <strong>{pupilName(form)}</strong> — {form.grade}, {form.section}, AY {form.school_year}.
          It will <strong>not</strong> be scanned, so no grades are saved.
        </Alert>
        <div className="btn-row">
          <Btn variant="success" onClick={handleSave} disabled={saving}>{saving ? 'Saving...' : 'Archive form'}</Btn>
          <Btn onClick={onBack} disabled={saving}>Back</Btn>
        </div>
      </Card>
    </div>
  )
}
