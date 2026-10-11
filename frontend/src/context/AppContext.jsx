import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { authAPI } from '../utils/api'

const AppContext = createContext(null)
const USER_REFRESH_MS = 3 * 60 * 1000

export function AppProvider({ children }) {
  const [loggedIn,   setLoggedIn]   = useState(false)
  const [user,       setUser]       = useState(null)
  const [activePage, setActivePage] = useState('dashboard')
  const [navParams,  setNavParams]  = useState({})
  // True while the sign-in cookie from before a page refresh is being checked with the server
  const [restoring,  setRestoring]  = useState(true)

  const login = useCallback((u) => { setUser(u); setLoggedIn(true) }, [])

  const logout = useCallback(() => {
    setUser(null); setLoggedIn(false); setActivePage('dashboard')
  }, [])

  // nav('detail', { recordId }) — params are read by the target page via navParams
  const nav = useCallback((page, params = {}) => {
    setNavParams(params); setActivePage(page)
  }, [])

  // Stay signed in across a refresh; no live cookie just shows the login screen
  useEffect(() => {
    authAPI.restore().then(u => u && login(u)).catch(() => {}).finally(() => setRestoring(false))
  }, [login])

  // The server decides what a user may do, so changes made by the OIC (a teacher's class, a role, a
  // deactivated account) are picked up while the app is open instead of at the next sign-in: when
  // the window is focused again, and every few minutes. A user who has been signed out returns to
  // the login screen. An unchanged user is not replaced, so screens do not reload for nothing.
  useEffect(() => {
    if (!loggedIn) return
    let stopped = false
    const refresh = () => {
      if (document.visibilityState === 'hidden') return
      authAPI.refresh().then(fresh => {
        if (stopped) return
        if (!fresh) { logout(); return }
        setUser(current => (JSON.stringify(current) === JSON.stringify(fresh) ? current : fresh))
      }).catch(() => {})   // offline: keep what we have
    }
    const timer = setInterval(refresh, USER_REFRESH_MS)
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      stopped = true
      clearInterval(timer)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [loggedIn, logout])

  const value = { loggedIn, restoring, user, login, logout, setUser, activePage, nav, navParams }
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export const useApp = () => useContext(AppContext)
