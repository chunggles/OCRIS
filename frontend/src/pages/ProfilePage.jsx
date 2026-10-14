import { useState } from 'react'
import { useApp } from '../context/AppContext'
import { Card, Btn, PageHeader } from '../components/ui/index'
import ChangePasswordModal from '../components/layout/ChangePasswordModal'
import { ROLE_LABELS } from '../data/constants'

export default function ProfilePage() {
  const { user } = useApp()
  const [changingPassword, setChangingPassword] = useState(false)
  return (
    <div>
      <PageHeader title="Profile" sub="Your account details and password"/>
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
      {changingPassword && <ChangePasswordModal onClose={() => setChangingPassword(false)}/>}
    </div>
  )
}
