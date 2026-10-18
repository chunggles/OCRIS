import { useState } from 'react'
import { useApp } from '../context/AppContext'
import { FormGroup } from '../components/ui/index'
import { authAPI } from '../utils/api'

const OFFLINE = "Can't reach the server. Check that OCRIS is running."

export default function LoginPage() {
  const { login, signOutNotice } = useApp()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [notice,   setNotice]   = useState(signOutNotice)   // e.g. signed out after a time without use
  const [loading,  setLoading]  = useState(false)
  // "Forgot password" swaps the password box for a request to the OIC
  const [forgot,   setForgot]   = useState(false)

  const handleLogin = async () => {
    setError(''); setLoading(true)
    try {
      login(await authAPI.login(username, password))
    } catch (e) {
      // 429: too many wrong passwords; the server says how long to wait
      setError(e?.offline ? OFFLINE : e?.status === 429 ? e.data.detail : 'Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  const handleForgot = async () => {
    if (!username.trim()) { setError('Enter your username first.'); return }
    setError(''); setNotice(''); setLoading(true)
    try {
      const data = await authAPI.forgotPassword(username.trim())
      setNotice(data.detail)
    } catch (e) {
      setError(e?.offline ? OFFLINE : e?.data?.detail || 'The request could not be sent.')
    } finally {
      setLoading(false)
    }
  }

  const switchMode = (value) => { setForgot(value); setError(''); setNotice('') }

  return (
    <div className="login-screen">
      <div className="login-wrap">
        <div className="login-top">
          <h1>OCRIS</h1>
          <p>Optical Character Recognition Information System<br/>Bayombong Central School, Nueva Vizcaya</p>
        </div>
        <div className="login-body">
          <FormGroup label="Username / Employee ID">
            <input className="fld" value={username} onChange={e => setUsername(e.target.value)}
              placeholder="Enter username" autoComplete="username"
              onKeyDown={e => e.key === 'Enter' && forgot && handleForgot()}/>
          </FormGroup>
          {!forgot && (
            <FormGroup label="Password">
              <input className="fld" type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Enter password" autoComplete="current-password"
                onKeyDown={e => e.key === 'Enter' && handleLogin()}/>
            </FormGroup>
          )}
          {forgot && (
            <div className="text-muted" style={{ fontSize: 12, marginBottom: 12 }}>
              OCRIS does not send email. Your request is shown to the OIC, who will give you a new temporary password.
            </div>
          )}
          {error && <div className="login-error">{error}</div>}
          {notice && <div className="login-error" style={{ background: 'var(--green-l)', color: 'var(--green)' }}>{notice}</div>}
          {forgot ? (
            <button className="login-btn" onClick={handleForgot} disabled={loading}>
              {loading ? 'Sending...' : 'Ask the OIC to reset my password'}
            </button>
          ) : (
            <button className="login-btn" onClick={handleLogin} disabled={loading}>
              {loading ? 'Signing in...' : 'Sign in to OCRIS'}
            </button>
          )}
          <div style={{ textAlign: 'center', marginTop: 12, fontSize: 12 }}>
            <a href="#" onClick={e => { e.preventDefault(); switchMode(!forgot) }}>
              {forgot ? 'Back to sign in' : 'Forgot your password?'}
            </a>
          </div>
          <div className="login-footer">
            Authorized BCS personnel only.<br/>Access monitored under RA 10173 — Data Privacy Act of 2012.
          </div>
        </div>
      </div>
    </div>
  )
}
