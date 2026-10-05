import { useCallback } from 'react'
import { GRADE_LEVELS } from '../../data/constants'
import { FormGroup } from '../../components/ui/index'
import { sectionsAPI, sectionsOf } from '../../utils/api'
import { useFetch } from '../../utils/useFetch'
import { useRecordOptions, withExtras } from '../../utils/useRecordOptions'

// A teacher's assigned grade and section. The section is typed in, with suggestions: the sections
// under the chosen grade level in the section tree, then any others that saved records use.
export default function ClassFields({ grade, section, onGrade, onSection }) {
  const options = useRecordOptions()
  const fetchTree = useCallback(() => sectionsAPI.tree(), [])
  const { data: sectionTree } = useFetch(fetchTree)
  const suggestions = withExtras(sectionsOf(sectionTree, grade).map(s => s.name), options.sections)
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
          {suggestions.map(s => <option key={s} value={s}/>)}
        </datalist>
      </FormGroup>
    </div>
  )
}
