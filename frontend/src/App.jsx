import { AppProvider, useApp } from './context/AppContext'
import Sidebar from './components/layout/Sidebar'
import Topbar  from './components/layout/Topbar'
import LoginPage        from './pages/LoginPage'
import DashboardPage    from './pages/DashboardPage'
import UploadPage       from './pages/UploadPage'
import RecordsPage      from './pages/RecordsPage'
import RecordDetailPage from './pages/RecordDetailPage'
import SearchPage       from './pages/SearchPage'
import AnalyticsPage    from './pages/AnalyticsPage'
import UsersPage        from './pages/UsersPage'
import AuditPage        from './pages/AuditPage'
import HistoryPage      from './pages/HistoryPage'

// Keys are the page names passed to nav() and used in NAV_ITEMS
const PAGES = {
  dashboard: DashboardPage,
  upload:    UploadPage,
  records:   RecordsPage,
  detail:    RecordDetailPage,
  search:    SearchPage,
  analytics: AnalyticsPage,
  users:     UsersPage,
  audit:     AuditPage,
  history:   HistoryPage,
}

function AppShell() {
  const { loggedIn, activePage } = useApp()
  if (!loggedIn) return <LoginPage/>
  const Page = PAGES[activePage] || DashboardPage
  return (
    <div className="app-shell">
      <Sidebar/>
      <div className="app-main">
        <Topbar/>
        <div className="page-wrap"><Page/></div>
      </div>
    </div>
  )
}

export default function App() {
  return <AppProvider><AppShell/></AppProvider>
}
