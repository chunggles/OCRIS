import { useState, useCallback } from 'react'
import { useApp } from '../context/AppContext'
import { ROLE_LABELS, ROLES, isStaffRole } from '../data/constants'
import { Card, Badge, Btn, StatusBanner, EmptyState, PageHeader, SearchInput } from '../components/ui/index'
import { usersAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { formatDate } from '../utils/format'
import AddUserForm      from './users/AddUserForm'
import EditUserModal    from './users/EditUserModal'
import PermissionMatrix from './users/PermissionMatrix'

// API user → table row
function toRow(u) {
  const staff = isStaffRole(u.role)
  return {
    user:       u,
    id:         u.id,
    name:      u.full_name || u.username,
    username:   u.username,
    roleCode:   u.role,
    roleLabel:  ROLE_LABELS[u.role] || 'Teacher',
    roleBadge:  staff ? 'b-blue' : 'b-grey',
    access:     u.assigned_grade && u.assigned_section
                  ? `${u.assigned_grade} — ${u.assigned_section}`
                  : staff ? 'Full system access' : 'No class assigned — sees no records',
    lastLogin:  u.last_login ? formatDate(u.last_login) : 'Never',
    isActive:   u.is_active !== false,
  }
}

const matches = (row, term) =>
  [row.name, row.username, row.roleLabel].some(v => v.toLowerCase().includes(term))

export default function UsersPage() {
  const { user: currentUser } = useApp()
  const [editing, setEditing] = useState(null)
  const [search,  setSearch]  = useState('')
  const canManage = currentUser?.role === ROLES.OIC  // Admin Staff can view the list only

  const fetchUsers = useCallback(() => usersAPI.list(), [])
  const { data, loading, error, refetch } = useFetch(fetchUsers)

  const rows     = Array.isArray(data) ? data.map(toRow) : []
  const filtered = rows.filter(r => matches(r, search.toLowerCase()))

  const handleDeactivate = async (row) => {
    if (!window.confirm(`Deactivate account for ${row.name}?\nThey will no longer be able to log in.`)) return
    try {
      if (row.id) await usersAPI.update(row.id, { is_active: false })
      refetch()
    } catch (e) {
      alert(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Deactivation failed.')
    }
  }

  const handleDelete = async (row) => {
    const prompt = `Permanently delete the account for ${row.name} (${row.username})?

` +
      'This cannot be undone. Records they uploaded are kept. To only block their login, use Deactivate instead.'
    if (!window.confirm(prompt)) return
    try {
      await usersAPI.delete(row.id)
      refetch()
    } catch (e) {
      alert(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Delete failed.')
    }
  }

  return (
    <div>
      <PageHeader title="User Management"/>
      <StatusBanner error={error} onRetry={refetch}/>

      <div className="g2" style={{ marginBottom: 16 }}>
        <PermissionMatrix/>
        {canManage && <AddUserForm onCreated={refetch}/>}
      </div>

      <Card
        title={`Users (${rows.length})`}
        action={
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <SearchInput value={search} onChange={setSearch} placeholder="Search name, username, role..." style={{ maxWidth: 220 }}/>
            <Btn size="sm" onClick={refetch}>↻</Btn>
          </div>
        }
      >
        {loading ? <StatusBanner loading/> : rows.length === 0 ? (
          <EmptyState>
            {error ? 'Could not load users.' : 'No users yet.'}
          </EmptyState>
        ) : (
          <table>
            <thead>
              <tr><th>Name</th><th>Username</th><th>Role</th><th>Class access</th><th>Last login</th><th>Status</th>{canManage && <th>Actions</th>}</tr>
            </thead>
            <tbody>
              {filtered.map(row => (
                <tr key={row.id ?? row.username}>
                  <td className="col-name">{row.name}</td>
                  <td className="mono-sm">{row.username}</td>
                  <td><Badge type={row.roleBadge}>{row.roleLabel}</Badge></td>
                  <td style={{ fontSize: 11 }}>{row.access}</td>
                  <td style={{ fontSize: 11 }}>{row.lastLogin}</td>
                  <td><Badge type={row.isActive ? 'b-green' : 'b-grey'}>{row.isActive ? 'Active' : 'Inactive'}</Badge></td>
                  {canManage && (
                    <td>
                      <div className="btn-row">
                        <Btn size="sm" onClick={() => setEditing(row.user)}>Edit</Btn>
                        {row.isActive && <Btn variant="danger" size="sm" onClick={() => handleDeactivate(row)}>Deactivate</Btn>}
                        {row.id !== currentUser?.id && <Btn variant="danger" size="sm" onClick={() => handleDelete(row)}>Delete</Btn>}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan="7" className="center text-muted" style={{ padding: '20px 0' }}>No users match "{search}"</td></tr>
              )}
            </tbody>
          </table>
        )}
      </Card>

      {editing && <EditUserModal user={editing} onClose={() => setEditing(null)} onSaved={refetch}/>}
    </div>
  )
}
