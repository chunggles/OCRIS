import { GRADE_LEVELS, SECTIONS } from '../../data/constants'
import { FormGroup } from '../../components/ui/index'
import { useRecordOptions, withExtras } from '../../utils/useRecordOptions'

// A teacher's assigned grade and section. The section is typed in, with suggestions,
// because it has to match the section typed on the upload form.
export default function ClassFields({ grade, section, onGrade, onSection }) {
  const options = useRecordOptions()
  return (
    <div className="form-row-2">
      <FormGroup label="Assigned grade *">
        <select className="fld" value={grade} onChange={e => onGrade(e.target.value)}>
          {withExtras(GRADE_LEVELS, [...options.grade_levels, grade].filter(Boolean)).map(g => <option key={g}>{g}</option>)}
        </select>
      </FormGroup>
      <FormGroup label="Assigned section *">
        <input className="fld" list="section-suggestions" value={section} onChange={e => onSection(e.target.value)} placeholder="e.g. Sampaguita"/>
        <datalist id="section-suggestions">
          {withExtras(SECTIONS, options.sections).map(s => <option key={s} value={s}/>)}
        </datalist>
      </FormGroup>
    </div>
  )
}
