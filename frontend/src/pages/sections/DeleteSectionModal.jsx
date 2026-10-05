import { useState } from 'react'
import { Btn, Notice } from '../../components/ui/index'
import { sectionsAPI } from '../../utils/api'

// Asks before deleting `section` (a section with the grade_level it sits under)
export default function DeleteSectionModal({ section, onClose, onDeleted }) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const handleDelete = async () => {
    setLoading(true); setError('')
    try {
      await sectionsAPI.delete(section.section_id)
      onDeleted()
      onClose()
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Delete failed.')
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <Notice type="error">{error}</Notice>

        <div className="confirm-text">Are you sure you want to delete this section?</div>
        <div className="confirm-target">{section.name} ({section.grade_level})</div>

        <div className="btn-row" style={{ marginTop: 18 }}>
          <Btn variant="delete" onClick={handleDelete} disabled={loading}>{loading ? 'Deleting...' : 'Delete'}</Btn>
          <Btn onClick={onClose}>Cancel</Btn>
        </div>
      </div>
    </div>
  )
}
