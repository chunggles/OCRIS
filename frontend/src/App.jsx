import { useState } from 'react'
import { AppProvider, useApp } from './context/AppContext'
import Sidebar from './components/layout/Sidebar'
import Topbar  from './components/layout/Topbar'
import { StatusBanner } from './components/ui/index'
import { canOpenPage } from './data/constants'
import LoginPage        from './pages/LoginPage'
import DashboardPage    from './pages/DashboardPage'
import UploadPage       from './pages/UploadPage'
import FillFormPage     from './pages/FillFormPage'
import RecordsPage      from './pages/RecordsPage'
import RecordDetailPage from './pages/RecordDetailPage'
import SearchPage       from './pages/SearchPage'
import AnalyticsPage    from './pages/AnalyticsPage'
import SectionsPage     from './pages/SectionsPage'
import UsersPage        from './pages/UsersPage'
import AuditPage        from './pages/AuditPage'
import HistoryPage      from './pages/HistoryPage'

// Keys are the page names passed to nav() and used in NAV_ITEMS
const PAGES = {
  dashboard: DashboardPage,
  upload:    UploadPage,
  fillform:  FillFormPage,
  records:   RecordsPage,
  detail:    RecordDetailPage,
  search:    SearchPage,
  analytics: AnalyticsPage,
  sections:  SectionsPage,
  users:     UsersPage,
  audit:    AuditPage,
  history:   HistoryPage,
}

function AppShell() {
  const { loggedIn, restoring, user, activePage } = useApp()
  // On a narrow screen the menu is off-screen until opened from the top bar
  const [menuOpen, setMenuOpen] = useState(false)
  if (restoring) return <StatusBanner loading/>
  if (!loggedIn) return <LoginPage/>
  // Pages a role may not open fall back to the dashboard; the server enforces the same rule
  const Page = (canOpenPage(activePage, user?.role) && PAGES[activePage]) || DashboardPage
  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)}/>
      <div className="app-main">
        <Topbar onMenu={() => setMenuOpen(true)}/>
        <div className="page-wrap"><Page/></div>
      </div>
    </div>
  )
}

export default function App() {
  return <AppProvider><AppShell/></AppProvider>
}
