import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { authAPI } from '../utils/api'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [loggedIn,   setLoggedIn]   = useState(false)
  const [user,       setUser]       = useState(null)
  const [activePage, setActivePage] = useState('dashboard')
  const [navParams,  setNavParams]  = useState({})
  // True while a stored session from before a page refresh is being checked with the server
  const [restoring,  setRestoring]  = useState(authAPI.hasSession)

  const login = useCallback((u) => { setUser(u); setLoggedIn(true) }, [])

  const logout = useCallback(() => {
    setUser(null); setLoggedIn(false); setActivePage('dashboard')
  }, [])

  // nav('detail', { recordId }) — params are read by the target page via navParams
  const nav = useCallback((page, params = {}) => {
    setNavParams(params); setActivePage(page)
  }, [])

  // Stay signed in across a refresh. An expired session gets a 401, which api.js sends to the login screen.
  useEffect(() => {
    if (!authAPI.hasSession()) return
    authAPI.me().then(login).catch(() => {}).finally(() => setRestoring(false))
  }, [login])

  const value = { loggedIn, restoring, user, login, logout, activePage, nav, navParams }
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export const useApp = () => useContext(AppContext)
