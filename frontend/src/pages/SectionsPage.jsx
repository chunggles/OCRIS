import { useState, useCallback } from 'react'
import { GRADE_LEVELS } from '../data/constants'
import { Card, Btn, IconBtn, StatusBanner, EmptyState, PageHeader } from '../components/ui/index'
import { sectionsAPI, gradeLevelsOf } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { plural } from '../utils/format'
import SectionModal from './sections/SectionModal'
import DeleteSectionModal from './sections/DeleteSectionModal'

// Shown until the tree has loaded, so the tabs don't jump
const EMPTY_TREE = GRADE_LEVELS.map(grade_level => ({ grade_level, sections: [] }))

export default function SectionsPage() {
  const [grade, setGrade] = useState(GRADE_LEVELS[0])
  const [modal, setModal] = useState(null)  // null (closed), {} (adding) or { section } (editing)
  const [deleting, setDeleting] = useState(null)  // the section awaiting delete confirmation

  const fetchTree = useCallback(() => sectionsAPI.tree(), [])
  const { data, loading, error, refetch } = useFetch(fetchTree)

  // The section tree: each grade level (a tab) is a parent node, and its sections (the tab's rows) are its children
  const tree   = Array.isArray(data) && data.length ? data : EMPTY_TREE
  const parent = tree.find(node => node.grade_level === grade) || tree[0]

  // Open the tab of the parent the section now sits under, in case it was added or moved elsewhere
  const handleSaved = (saved) => {
    if (saved?.grade_level) setGrade(saved.grade_level)
    refetch()
  }

  return (
    <div>
      <PageHeader title="Sections"/>
      <StatusBanner error={error} onRetry={refetch}/>

      <div className="tabs" role="tablist">
        {tree.map(node => (
          <button key={node.grade_level} role="tab" aria-selected={node === parent}
            className={`tab${node === parent ? ' active' : ''}`} onClick={() => setGrade(node.grade_level)}>
            {node.grade_level}<span className="tab-count">{node.sections.length}</span>
          </button>
        ))}
      </div>

      <Card
        title={`${parent.grade_level} — ${plural(parent.sections.length, 'section')}`}
        action={<Btn variant="primary" size="sm" onClick={() => setModal({})}>+ Add Section</Btn>}
      >
        {loading ? <StatusBanner loading/> : parent.sections.length === 0 ? (
          <EmptyState>
            {error ? 'Could not load sections.' : `No sections in ${parent.grade_level} yet.`}
          </EmptyState>
        ) : parent.sections.map(child => ({ ...child, grade_level: parent.grade_level })).map(section => (
          <div key={section.section_id} className="section-item">
            <div className="section-name">{section.name}</div>
            <div className="section-actions">
              <IconBtn icon="pencil" label={`Edit ${section.name}`} onClick={() => setModal({ section })}/>
              <IconBtn icon="trash" label={`Delete ${section.name}`} variant="danger" onClick={() => setDeleting(section)}/>
            </div>
          </div>
        ))}
      </Card>

      {modal && (
        <SectionModal section={modal.section} gradeLevels={gradeLevelsOf(tree)} defaultGrade={parent.grade_level}
          onClose={() => setModal(null)} onSaved={handleSaved}/>
      )}
      {deleting && <DeleteSectionModal section={deleting} onClose={() => setDeleting(null)} onDeleted={refetch}/>}
    </div>
  )
}
