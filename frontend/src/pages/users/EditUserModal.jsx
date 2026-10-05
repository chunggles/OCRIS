import { useState } from 'react'
import { GRADE_LEVELS, ROLES } from '../../data/constants'
import { Btn, FormGroup, Notice } from '../../components/ui/index'
import { usersAPI } from '../../utils/api'
import RoleSelect from './RoleSelect'
import ClassFields from './ClassFields'

const CLOSE_DELAY_MS = 700
const MIN_PASSWORD = 8

// First error message in an API error body: {detail: "..."} or {field: ["..."]}
const firstError = (data) => data?.detail || Object.values(data || {}).flat()[0]

// `user` is the account as returned by the API
export default function EditUserModal({ user, onClose, onSaved }) {
  const [form, setForm] = useState({
    first_name: user.first_name || '',
    last_name:  user.last_name || '',
    role:       user.role || ROLES.TEACHER,
    active:     user.is_active !== false,
    grade:      user.assigned_grade || GRADE_LEVELS[GRADE_LEVELS.length - 1],
    section:    user.assigned_section || '',
    password:   '',
  })
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error,   setError]   = useState('')

  const set = (key, value) => setForm(f => ({ ...f, [key]: value }))
  const isTeacher = form.role === ROLES.TEACHER

  const handleSave = async () => {
    if (isTeacher && !form.section.trim()) { setError('A teacher needs an assigned section.'); return }
    if (form.password && form.password.length < MIN_PASSWORD) { setError(`The new password must be at least ${MIN_PASSWORD} characters.`); return }
    setLoading(true); setError('')
    try {
      await usersAPI.update(user.id, {
        first_name:       form.first_name.trim(),
        last_name:        form.last_name.trim(),
        role:             form.role,
        is_active:        form.active,
        assigned_grade:   isTeacher ? form.grade : null,
        assigned_section: isTeacher ? form.section.trim() : null,
        ...(form.password && { password: form.password }),
      })
      setMessage('Changes saved.')
      setTimeout(() => { onSaved(); onClose() }, CLOSE_DELAY_MS)
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Try again in a moment." : firstError(e?.data) || 'Save failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-title">Edit user</div>
        <div className="modal-sub">{user.username}</div>

        <Notice type="success">{message}</Notice>
        <Notice type="error">{error}</Notice>

        <div className="form-row-2">
          <FormGroup label="Last name">
            <input className="fld" value={form.last_name} onChange={e => set('last_name', e.target.value)}/>
          </FormGroup>
          <FormGroup label="First name">
            <input className="fld" value={form.first_name} onChange={e => set('first_name', e.target.value)}/>
          </FormGroup>
        </div>
        <FormGroup label="Role">
          <RoleSelect value={form.role} onChange={v => set('role', v)}/>
        </FormGroup>
        {isTeacher && (
          <ClassFields grade={form.grade} section={form.section} onGrade={v => set('grade', v)} onSection={v => set('section', v)}/>
        )}
        <FormGroup label="Account status">
          <select className="fld" value={form.active ? 'active' : 'inactive'} onChange={e => set('active', e.target.value === 'active')}>
            <option value="active">Active</option>
            <option value="inactive">Deactivated</option>
          </select>
        </FormGroup>
        <FormGroup label="New password (leave blank to keep the current one)">
          <input className="fld" type="password" value={form.password} onChange={e => set('password', e.target.value)}
            placeholder={`Min. ${MIN_PASSWORD} characters`} autoComplete="new-password"/>
        </FormGroup>

        <div className="btn-row" style={{ marginTop: 16 }}>
          <Btn variant="primary" onClick={handleSave} disabled={loading}>{loading ? 'Saving...' : 'Save changes'}</Btn>
          <Btn onClick={onClose}>Cancel</Btn>
        </div>
      </div>
    </div>
  )
}
