import { useApp } from '../../context/AppContext'
import { navItemsFor } from '../../data/constants'

const initialsOf = (name) => name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()

export default function Sidebar() {
  const { activePage, nav, user } = useApp()
  const name = user?.full_name || user?.username || ''

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-name">OCRIS</div>
        <div className="logo-sub">Bayombong Central School<br/>Record Management System</div>
      </div>
      <nav className="sidebar-nav">
        {navItemsFor(user?.role).map((item, i) => item.section
          ? <div key={i} className="nav-section">{item.section}</div>
          : (
            <div key={item.key} className={`nav-item${activePage === item.key ? ' active' : ''}`} onClick={() => nav(item.key)}>
              {item.label}
            </div>
          )
        )}
      </nav>
      <div className="sidebar-user">
        <div className="avatar">{initialsOf(name)}</div>
        <div>
          <div className="sidebar-user-name">{name}</div>
          <div className="sidebar-user-role">{user?.role}</div>
        </div>
      </div>
    </div>
  )
}
