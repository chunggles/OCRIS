import { useState } from 'react'
import { useApp } from '../../context/AppContext'
import { PAGE_TITLES } from '../../data/constants'
import { Btn } from '../ui/index'
import { authAPI } from '../../utils/api'
import ChangePasswordModal from './ChangePasswordModal'

// `onMenu` opens the menu on narrow screens, where the button is shown
export default function Topbar({ onMenu }) {
  const { activePage, logout } = useApp()
  const [changingPassword, setChangingPassword] = useState(false)
  // Invalidate the server token too, not just the local session
  const handleSignOut = async () => { await authAPI.logout(); logout() }
  return (
    <div className="topbar">
      <div className="topbar-title">
        <button className="menu-btn" onClick={onMenu} aria-label="Open menu">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
        <div className="breadcrumb"><strong>{PAGE_TITLES[activePage] || activePage}</strong></div>
      </div>
      <div className="topbar-actions">
        <Btn variant="secondary" size="sm" onClick={() => setChangingPassword(true)}>Change password</Btn>
        <Btn variant="secondary" size="sm" onClick={handleSignOut}>Sign out</Btn>
      </div>
      {changingPassword && <ChangePasswordModal onClose={() => setChangingPassword(false)}/>}
    </div>
  )
}
