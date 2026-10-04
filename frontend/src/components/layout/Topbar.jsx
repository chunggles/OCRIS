import { useApp } from '../../context/AppContext'
import { PAGE_TITLES } from '../../data/constants'
import { Btn } from '../ui/index'
import { authAPI } from '../../utils/api'

export default function Topbar() {
  const { activePage, logout } = useApp()
  // Invalidate the server token too, not just the local session
  const handleSignOut = async () => { await authAPI.logout(); logout() }
  return (
    <div className="topbar">
      <div className="breadcrumb"><strong>{PAGE_TITLES[activePage] || activePage}</strong></div>
      <div className="topbar-actions">
        <Btn variant="secondary" size="sm" onClick={handleSignOut}>Sign out</Btn>
      </div>
    </div>
  )
}
