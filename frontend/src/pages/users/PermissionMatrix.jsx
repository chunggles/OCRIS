import { PERM_MATRIX } from '../../data/constants'
import { Card } from '../../components/ui/index'

function PermCell({ value }) {
  if (value === true)  return <td className="perm-yes">Yes</td>
  if (value === false) return <td className="perm-no">No</td>
  return <td className="perm-cond">{value}</td>
}

export default function PermissionMatrix() {
  return (
    <Card title="Role permission matrix">
      <table>
        <thead>
          <tr>
            <th>Permission</th>
            <th className="center">OIC</th>
            <th className="center">Admin Staff</th>
            <th className="center">Teacher</th>
          </tr>
        </thead>
        <tbody>
          {PERM_MATRIX.map(p => (
            <tr key={p.perm}>
              <td>{p.perm}</td>
              <PermCell value={p.oic}/>
              <PermCell value={p.admin}/>
              <PermCell value={p.teacher}/>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
