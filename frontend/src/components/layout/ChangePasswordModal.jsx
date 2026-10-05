import { useState } from 'react'
import { Btn, FormGroup, Notice } from '../ui/index'
import { authAPI } from '../../utils/api'

const MIN_PASSWORD = 8
const CLOSE_DELAY_MS = 900

export default function ChangePasswordModal({ onClose }) {
  const [current, setCurrent] = useState('')
  const [next,    setNext]    = useState('')
  const [repeat,  setRepeat]  = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error,   setError]   = useState('')

  const handleSave = async () => {
    if (!current) { setError('Enter your current password.'); return }
    if (next.length < MIN_PASSWORD) { setError(`The new password must be at least ${MIN_PASSWORD} characters.`); return }
    if (next !== repeat) { setError('The two new passwords do not match.'); return }
    setLoading(true); setError('')
    try {
      await authAPI.changePassword(current, next)
      setMessage('Password changed.')
      setTimeout(onClose, CLOSE_DELAY_MS)
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Could not change the password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-title">Change password</div>
        <div className="modal-sub">Use at least {MIN_PASSWORD} characters.</div>

        <Notice type="success">{message}</Notice>
        <Notice type="error">{error}</Notice>

        <FormGroup label="Current password">
          <input className="fld" type="password" value={current} onChange={e => setCurrent(e.target.value)} autoComplete="current-password"/>
        </FormGroup>
        <FormGroup label="New password">
          <input className="fld" type="password" value={next} onChange={e => setNext(e.target.value)} autoComplete="new-password"/>
        </FormGroup>
        <FormGroup label="Repeat new password">
          <input className="fld" type="password" value={repeat} onChange={e => setRepeat(e.target.value)} autoComplete="new-password"
            onKeyDown={e => e.key === 'Enter' && handleSave()}/>
        </FormGroup>

        <div className="btn-row" style={{ marginTop: 16 }}>
          <Btn variant="primary" onClick={handleSave} disabled={loading}>{loading ? 'Saving...' : 'Change password'}</Btn>
          <Btn onClick={onClose}>Cancel</Btn>
        </div>
      </div>
    </div>
  )
}
