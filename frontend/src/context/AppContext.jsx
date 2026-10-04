import { createContext, useContext, useState, useCallback } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [loggedIn,   setLoggedIn]   = useState(false)
  const [user,       setUser]       = useState(null)
  const [activePage, setActivePage] = useState('dashboard')
  const [navParams,  setNavParams]  = useState({})

  const login = useCallback((u) => { setUser(u); setLoggedIn(true) }, [])

  const logout = useCallback(() => {
    setUser(null); setLoggedIn(false); setActivePage('dashboard')
  }, [])

  // nav('detail', { recordId }) — params are read by the target page via navParams
  const nav = useCallback((page, params = {}) => {
    setNavParams(params); setActivePage(page)
  }, [])

  const value = { loggedIn, user, login, logout, activePage, nav, navParams }
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export const useApp = () => useContext(AppContext)
