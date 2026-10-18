import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import { authAPI } from '../utils/api'

const AppContext = createContext(null)
const USER_REFRESH_MS = 3 * 60 * 1000
// Typing, clicking, scrolling or touching anywhere in the app counts as use of the session
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'wheel', 'touchstart']
const IDLE_CHECK_MS = 30 * 1000

export function AppProvider({ children }) {
  const [loggedIn,   setLoggedIn]   = useState(false)
  const [user,       setUser]       = useState(null)
  const [activePage, setActivePage] = useState('dashboard')
  const [navParams,  setNavParams]  = useState({})
  // True while the sign-in cookie from before a page refresh is being checked with the server
  const [restoring,  setRestoring]  = useState(true)
  // Why the user was returned to the login screen, shown there; empty when they signed out themselves
  const [signOutNotice, setSignOutNotice] = useState('')
  const lastActivity = useRef(Date.now())

  const login = useCallback((u) => {
    lastActivity.current = Date.now()
    setUser(u); setLoggedIn(true); setSignOutNotice('')
  }, [])

  const logout = useCallback((notice = '') => {
    setUser(null); setLoggedIn(false); setActivePage('dashboard'); setSignOutNotice(notice)
  }, [])

  // nav('detail', { recordId }) — params are read by the target page via navParams
  const nav = useCallback((page, params = {}) => {
    setNavParams(params); setActivePage(page)
  }, [])

  // Stay signed in across a refresh; no live cookie just shows the login screen
  useEffect(() => {
    authAPI.restore().then(u => u && login(u)).catch(() => {}).finally(() => setRestoring(false))
  }, [login])

  useEffect(() => {
    if (!loggedIn) return
    const mark = () => { lastActivity.current = Date.now() }
    ACTIVITY_EVENTS.forEach(e => window.addEventListener(e, mark, { capture: true, passive: true }))
    return () => ACTIVITY_EVENTS.forEach(e => window.removeEventListener(e, mark, { capture: true }))
  }, [loggedIn])

  // The server decides what a user may do, so changes made by the OIC (a teacher's class, a role, a
  // deactivated account) are picked up while the app is open instead of at the next sign-in: when
  // the window is focused again, and every few minutes. A user who has been signed out returns to
  // the login screen. An unchanged user is not replaced, so screens do not reload for nothing.
  //
  // The same refresh keeps the session alive while the app is in use: it tells the server whether
  // the user typed or clicked since the last one (a long form makes no requests while it is typed).
  // The server ends a session unused for idle_timeout_minutes; once that much time has passed here
  // without use, the app asks at once instead of waiting for the next refresh.
  const idleMinutes = user?.idle_timeout_minutes || 0
  useEffect(() => {
    if (!loggedIn) return
    let stopped = false
    let reportedAt = Date.now()   // use up to this moment has been reported to the server
    const idleMs = idleMinutes * 60 * 1000
    const idleNow = () => idleMs > 0 && Date.now() - lastActivity.current >= idleMs
    const idleNotice = `You were signed out after ${idleMinutes} minutes without use. Sign in again to continue.`
    const refresh = () => {
      if (document.visibilityState === 'hidden') return
      const used = lastActivity.current > reportedAt
      const askedAt = Date.now()
      authAPI.refresh({ background: !used }).then(fresh => {
        if (stopped) return
        if (!fresh) {
          logout(idleNow() ? idleNotice : 'Your session has ended. Sign in again to continue.')
          return
        }
        if (used) reportedAt = askedAt
        setUser(current => (JSON.stringify(current) === JSON.stringify(fresh) ? current : fresh))
      }).catch(() => {
        // offline or a server error: keep what we have, unless the idle limit has passed, as the server
        // has ended the session then anyway and the records must not stay on screen
        if (!stopped && idleNow()) logout(idleNotice)
      })
    }
    // with a short idle limit the refresh comes often enough to report use well before it
    const timer = setInterval(refresh, idleMs ? Math.min(USER_REFRESH_MS, idleMs / 3) : USER_REFRESH_MS)
    const idleTimer = idleMs ? setInterval(() => { if (idleNow()) refresh() }, IDLE_CHECK_MS) : null
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      stopped = true
      clearInterval(timer)
      if (idleTimer) clearInterval(idleTimer)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [loggedIn, logout, idleMinutes])

  const value = { loggedIn, restoring, user, login, logout, setUser, activePage, nav, navParams, signOutNotice }
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export const useApp = () => useContext(AppContext)
