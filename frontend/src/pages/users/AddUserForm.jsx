import { useState } from 'react'
import { ROLES } from '../../data/constants'
import { Card, Btn, FormGroup, Notice } from '../../components/ui/index'
import { usersAPI } from '../../utils/api'
import RoleSelect from './RoleSelect'
import ClassFields from './ClassFields'

const BLANK_FORM = {
  last_name: '', first_name: '', username: '', role: ROLES.TEACHER,
  assigned_grade: 'Grade 6', assigned_section: '', password: '',
}
const MIN_PASSWORD = 8

function validate(form) {
  if (!form.last_name.trim())  return 'Last name is required.'
  if (!form.first_name.trim()) return 'First name is required.'
  if (!form.username.trim())   return 'Username is required.'
  if (form.role === ROLES.TEACHER && !form.assigned_section.trim()) return 'A teacher needs an assigned section.'
  if (!form.password)          return 'Password is required.'
  if (form.password.length < MIN_PASSWORD) return `Password must be at least ${MIN_PASSWORD} characters.`
  return null
}

function toPayload(form) {
  const isTeacher = form.role === ROLES.TEACHER
  const username  = form.username.trim()
  return {
    last_name:        form.last_name.trim(),
    first_name:       form.first_name.trim(),
    username,
    password:         form.password,
    role:             form.role,
    employee_id:      username,
    assigned_grade:   isTeacher ? form.assigned_grade : null,
    assigned_section: isTeacher ? form.assigned_section.trim() : null,
  }
}

export default function AddUserForm({ onCreated }) {
  const [form,    setForm]    = useState(BLANK_FORM)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState('')
  const [error,   setError]   = useState('')

  const set = (key, value) => setForm(f => ({ ...f, [key]: value }))

  const handleCreate = async () => {
    const problem = validate(form)
    if (problem) { setError(problem); return }
    setError(''); setSuccess(''); setLoading(true)
    try {
      await usersAPI.create(toPayload(form))
      setSuccess(`Account created: ${form.last_name}, ${form.first_name} (${form.role})`)
      setForm(BLANK_FORM)
      onCreated?.()
    } catch (e) {
      setError(e?.offline
        ? "Can't reach the server. Try again in a moment."
        : e?.data?.username?.[0] || e?.data?.detail || JSON.stringify(e?.data) || 'Failed to create account.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card title="Add new user account">
      <Notice type="error">{error}</Notice>
      <Notice type="success">{success}</Notice>

      <div className="form-row-2">
        <FormGroup label="Last name *">
          <input className="fld" value={form.last_name} onChange={e => set('last_name', e.target.value)} placeholder="e.g. Ramos"/>
        </FormGroup>
        <FormGroup label="First name *">
          <input className="fld" value={form.first_name} onChange={e => set('first_name', e.target.value)} placeholder="e.g. Gloria D."/>
        </FormGroup>
      </div>

      <FormGroup label="Username / Employee ID *">
        <input className="fld" value={form.username} onChange={e => set('username', e.target.value)} placeholder="e.g. g.ramos"/>
      </FormGroup>

      <FormGroup label="Role *">
        <RoleSelect value={form.role} onChange={v => set('role', v)}/>
      </FormGroup>

      {form.role === ROLES.TEACHER && (
        <ClassFields
          grade={form.assigned_grade} section={form.assigned_section}
          onGrade={v => set('assigned_grade', v)} onSection={v => set('assigned_section', v)}/>
      )}

      <FormGroup label={`Temporary password * (min. ${MIN_PASSWORD} characters)`}>
        <input className="fld" type="password" value={form.password} onChange={e => set('password', e.target.value)} placeholder={`Min. ${MIN_PASSWORD} characters`}/>
      </FormGroup>

      <Btn variant="primary" onClick={handleCreate} disabled={loading}>
        {loading ? 'Creating account...' : 'Create account'}
      </Btn>
    </Card>
  )
}
