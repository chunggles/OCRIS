import { useState } from 'react'
import { GRADE_LEVELS } from '../../data/constants'
import { Btn, FormGroup, Notice } from '../../components/ui/index'
import { sectionsAPI } from '../../utils/api'

// Adds a section under a grade level, or edits `section` when one is given. `gradeLevels` are the
// parent nodes it can sit under; `defaultGrade` preselects the one for a new section.
export default function SectionModal({ section, gradeLevels = GRADE_LEVELS, defaultGrade = gradeLevels[0], onClose, onSaved }) {
  const editing = Boolean(section)
  const [name,    setName]    = useState(section?.name || '')
  const [grade,   setGrade]   = useState(section?.grade_level || defaultGrade)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const handleSave = async () => {
    if (!name.trim()) { setError('Enter a section name.'); return }
    setLoading(true); setError('')
    try {
      const body  = { name: name.trim(), grade_level: grade }
      const saved = editing ? await sectionsAPI.update(section.section_id, body) : await sectionsAPI.create(body)
      onSaved(saved)
      onClose()
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Could not save the section.')
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-title" style={{ marginBottom: 18 }}>{editing ? 'Edit Section' : 'Add Section'}</div>

        <Notice type="error">{error}</Notice>

        <FormGroup label="Section Name:">
          <input className="fld" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Sampaguita" maxLength={50} autoFocus
            onKeyDown={e => e.key === 'Enter' && handleSave()}/>
        </FormGroup>
        <FormGroup label="Grade Level:">
          <select className="fld" value={grade} onChange={e => setGrade(e.target.value)}>
            {gradeLevels.map(g => <option key={g}>{g}</option>)}
          </select>
        </FormGroup>

        <div className="btn-row" style={{ marginTop: 16 }}>
          <Btn variant="primary" onClick={handleSave} disabled={loading}>
            {loading ? 'Saving...' : editing ? 'Save changes' : 'Add Section'}
          </Btn>
          <Btn onClick={onClose}>Cancel</Btn>
        </div>
      </div>
    </div>
  )
}
