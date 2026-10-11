import { useState } from 'react'
import { Btn, FormGroup, Notice } from '../ui/index'
import { PASSWORD_RULES, passwordProblem } from '../../data/constants'
import { authAPI } from '../../utils/api'

const CLOSE_DELAY_MS = 900

// `forced`: the user signed in with a temporary password and cannot do anything else until it is
// replaced, so the window has no Cancel; `onChanged` receives the updated user.
export default function ChangePasswordModal({ onClose, forced = false, onChanged }) {
  const [current, setCurrent] = useState('')
  const [next,    setNext]    = useState('')
  const [repeat,  setRepeat]  = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error,   setError]   = useState('')

  const handleSave = async () => {
    if (!current) { setError('Enter your current password.'); return }
    const weak = passwordProblem(next)
    if (weak) { setError(weak); return }
    if (next !== repeat) { setError('The two new passwords do not match.'); return }
    setLoading(true); setError('')
    try {
      const result = await authAPI.changePassword(current, next)
      setMessage('Password changed.')
      setTimeout(() => { onChanged?.(result.user); onClose?.() }, CLOSE_DELAY_MS)
    } catch (e) {
      setError(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Could not change the password.')
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-title">{forced ? 'Choose your own password' : 'Change password'}</div>
        <div className="modal-sub">
          {forced ? 'You signed in with a temporary password. Replace it to continue. ' : ''}{PASSWORD_RULES}
        </div>

        <Notice type="success">{message}</Notice>
        <Notice type="error">{error}</Notice>

        <FormGroup label={forced ? 'Temporary password' : 'Current password'}>
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
          {!forced && <Btn onClick={onClose}>Cancel</Btn>}
        </div>
      </div>
    </div>
  )
}
