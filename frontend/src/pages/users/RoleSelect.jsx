import { ROLE_OPTIONS } from '../../data/constants'

export default function RoleSelect({ value, onChange }) {
  return (
    <select className="fld" value={value} onChange={e => onChange(e.target.value)}>
      {ROLE_OPTIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
    </select>
  )
}
