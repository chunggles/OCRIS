import { useState } from 'react'
import { ROLES } from '../../data/constants'
import { Btn, FormGroup, Notice } from '../../components/ui/index'
import { usersAPI } from '../../utils/api'
import RoleSelect from './RoleSelect'

const CLOSE_DELAY_MS = 700

export default function EditUserModal({ user, onClose, onSaved }) {
  const [role,    setRole]    = useState(user.roleCode || ROLES.TEACHER)
  const [active,  setActive]  = useState(user.isActive)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error,   setError]   = useState('')

  const handleSave = async () => {
    setLoading(true); setError('')
    try {
      if (user.id) await usersAPI.update(user.id, { role, is_active: active })
      setMessage('Changes saved.')
      setTimeout(() => { onSaved(); onClose() }, CLOSE_DELAY_MS)
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Save failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-title">Edit user</div>
        <div className="modal-sub">{user.name}</div>

        <Notice type="success">{message}</Notice>
        <Notice type="error">{error}</Notice>

        <FormGroup label="Role">
          <RoleSelect value={role} onChange={setRole}/>
        </FormGroup>
        <FormGroup label="Account status">
          <select className="fld" value={active ? 'active' : 'inactive'} onChange={e => setActive(e.target.value === 'active')}>
            <option value="active">Active</option>
            <option value="inactive">Deactivated</option>
          </select>
        </FormGroup>

        <div className="btn-row" style={{ marginTop: 16 }}>
          <Btn variant="primary" onClick={handleSave} disabled={loading}>{loading ? 'Saving...' : 'Save changes'}</Btn>
          <Btn onClick={onClose}>Cancel</Btn>
        </div>
      </div>
    </div>
  )
}
