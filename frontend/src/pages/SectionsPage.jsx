import { useState, useCallback } from 'react'
import { GRADE_LEVELS } from '../data/constants'
import { Card, Btn, IconBtn, StatusBanner, EmptyState, PageHeader } from '../components/ui/index'
import { sectionsAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { plural } from '../utils/format'
import SectionModal from './sections/SectionModal'

export default function SectionsPage() {
  const [grade, setGrade] = useState(GRADE_LEVELS[0])
  const [modal, setModal] = useState(null)  // null (closed), {} (adding) or { section } (editing)

  const fetchSections = useCallback(() => sectionsAPI.list(), [])
  const { data, loading, error, refetch } = useFetch(fetchSections)

  const sections = Array.isArray(data) ? data : []
  const inGrade  = (g) => sections.filter(s => s.grade_level === g)
  const shown    = inGrade(grade)

  // Show the tab the section was saved under, in case its grade level was changed
  const handleSaved = (saved) => {
    if (saved?.grade_level) setGrade(saved.grade_level)
    refetch()
  }

  const handleDelete = async (section) => {
    const prompt = `Delete the section ${section.name} from ${section.grade_level}?

` +
      'Records and teacher accounts that use this section are not changed.'
    if (!window.confirm(prompt)) return
    try {
      await sectionsAPI.delete(section.section_id)
      refetch()
    } catch (e) {
      alert(e?.offline ? "Can't reach the server. Try again in a moment." : e?.data?.detail || 'Delete failed.')
    }
  }

  return (
    <div>
      <PageHeader title="Sections"/>
      <StatusBanner error={error} onRetry={refetch}/>

      <div className="tabs" role="tablist">
        {GRADE_LEVELS.map(g => (
          <button key={g} role="tab" aria-selected={g === grade} className={`tab${g === grade ? ' active' : ''}`} onClick={() => setGrade(g)}>
            {g}<span className="tab-count">{inGrade(g).length}</span>
          </button>
        ))}
      </div>

      <Card
        title={`${grade} — ${plural(shown.length, 'section')}`}
        action={<Btn variant="primary" size="sm" onClick={() => setModal({})}>+ Add Section</Btn>}
      >
        {loading ? <StatusBanner loading/> : shown.length === 0 ? (
          <EmptyState>
            {error ? 'Could not load sections.' : `No sections in ${grade} yet.`}
          </EmptyState>
        ) : shown.map(section => (
          <div key={section.section_id} className="section-item">
            <div className="section-name">{section.name}</div>
            <div className="section-actions">
              <IconBtn icon="pencil" label={`Edit ${section.name}`} onClick={() => setModal({ section })}/>
              <IconBtn icon="trash" label={`Delete ${section.name}`} variant="danger" onClick={() => handleDelete(section)}/>
            </div>
          </div>
        ))}
      </Card>

      {modal && <SectionModal section={modal.section} defaultGrade={grade} onClose={() => setModal(null)} onSaved={handleSaved}/>}
    </div>
  )
}
