import { useCallback } from 'react'
import { GRADE_LEVELS } from '../../data/constants'
import { FormGroup } from '../../components/ui/index'
import { sectionsAPI, sectionsOf } from '../../utils/api'
import { useFetch } from '../../utils/useFetch'
import { useRecordOptions, withExtras } from '../../utils/useRecordOptions'

// A teacher's assigned grade and section. The section is chosen from the sections under the grade
// level in the section tree, the same list the upload form uses, so the two always match.
export default function ClassFields({ grade, section, onGrade, onSection }) {
  const options = useRecordOptions()
  const fetchTree = useCallback(() => sectionsAPI.tree(), [])
  const { data: sectionTree, loading } = useFetch(fetchTree)

  const names  = sectionsOf(sectionTree, grade).map(s => s.name)
  // An account saved with a section that has since been renamed or deleted still shows it
  const legacy = section && !loading && !names.includes(section)

  // Sections belong to a grade level, so changing the grade clears the chosen section
  const handleGrade = (value) => { onGrade(value); onSection('') }

  return (
    <div className="form-row-2">
      <FormGroup label="Assigned grade *">
        <select className="fld" value={grade} onChange={e => handleGrade(e.target.value)}>
          {withExtras(GRADE_LEVELS, [...options.grade_levels, grade].filter(Boolean)).map(g => <option key={g}>{g}</option>)}
        </select>
      </FormGroup>
      <FormGroup label="Assigned section *">
        <select className="fld" value={section} onChange={e => onSection(e.target.value)}>
          <option value="">{loading ? 'Loading...' : names.length ? 'Select a section' : `No sections in ${grade}`}</option>
          {legacy && <option value={section}>{section} (not in Sections)</option>}
          {names.map(s => <option key={s}>{s}</option>)}
        </select>
      </FormGroup>
    </div>
  )
}
