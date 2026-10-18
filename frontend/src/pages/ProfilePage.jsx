import { useState } from 'react'
import { useApp } from '../context/AppContext'
import { Card, Btn, PageHeader } from '../components/ui/index'
import { authAPI } from '../utils/api'
import ChangePasswordModal from '../components/layout/ChangePasswordModal'
import { ROLE_LABELS } from '../data/constants'

export default function ProfilePage() {
  const { user, logout } = useApp()
  const [changingPassword, setChangingPassword] = useState(false)
  const [signingOut, setSigningOut] = useState(false)

  // For a computer left signed in elsewhere, or a password that may be known to someone else
  const signOutEverywhere = async () => {
    if (!window.confirm('Sign out of OCRIS on every computer and phone, this one included?')) return
    setSigningOut(true)
    await authAPI.logoutAll()
    logout('You were signed out of every device.')
  }
  return (
    <div>
      <PageHeader title="Profile" sub="Your account details, password and sign-ins"/>
      <Card title="Account">
        <div style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '8px 24px', fontSize: 13 }}>
          <span className="text-3">Name</span><span>{user?.full_name || '—'}</span>
          <span className="text-3">Username</span><span>{user?.username || '—'}</span>
          <span className="text-3">Role</span><span>{ROLE_LABELS[user?.role] || user?.role || '—'}</span>
        </div>
        <div className="btn-row" style={{ marginTop: 16 }}>
          <Btn variant="primary" onClick={() => setChangingPassword(true)}>Change password</Btn>
        </div>
      </Card>
      <Card title="Sign-ins">
        <div style={{ fontSize: 13 }}>
          You can be signed in on several computers at once.{user?.idle_timeout_minutes ? ` A sign-in ends by itself after ${user.idle_timeout_minutes} minutes without use.` : ''}
          {' '}If you left OCRIS open on another computer, or think someone else knows your password, sign out everywhere (and change your password).
        </div>
        <div className="btn-row" style={{ marginTop: 16 }}>
          <Btn variant="danger" onClick={signOutEverywhere} disabled={signingOut}>{signingOut ? 'Signing out...' : 'Sign out of every device'}</Btn>
        </div>
      </Card>
      {changingPassword && <ChangePasswordModal onClose={() => setChangingPassword(false)}/>}
    </div>
  )
}
