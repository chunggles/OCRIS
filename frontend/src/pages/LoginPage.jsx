import { useState } from 'react'
import { useApp } from '../context/AppContext'
import { FormGroup } from '../components/ui/index'
import { authAPI } from '../utils/api'

export default function LoginPage() {
  const { login } = useApp()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const handleLogin = async () => {
    setError(''); setLoading(true)
    try {
      login(await authAPI.login(username, password))
    } catch (e) {
      setError(e?.offline
        ? "Can't reach the server. Check that OCRIS is running."
        : 'Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

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
              placeholder="Enter username" autoComplete="off"/>
          </FormGroup>
          <FormGroup label="Password">
            <input className="fld" type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="Enter password" autoComplete="new-password"
              onKeyDown={e => e.key === 'Enter' && handleLogin()}/>
          </FormGroup>
          {error && <div className="login-error">{error}</div>}
          <button className="login-btn" onClick={handleLogin} disabled={loading}>
            {loading ? 'Signing in...' : 'Sign in to OCRIS'}
          </button>
          <div className="login-footer">
            Authorized BCS personnel only.<br/>Access monitored under RA 10173 — Data Privacy Act of 2012.
          </div>
        </div>
      </div>
    </div>
  )
}
