import { useCallback } from 'react'
import { useApp } from '../context/AppContext'
import { GRADE_LEVELS, ROLES } from '../data/constants'
import { sectionsAPI, gradeLevelsOf, sectionsOf } from './api'
import { useFetch } from './useFetch'

export const NO_CLASS = 'Your account has no class assigned yet. Ask the OIC to assign your grade and section.'

// The class a form is filed under, given the grade and section chosen so far. Both choices follow
// the section tree: the grade levels are its parent nodes and the sections are the children of the
// chosen grade. A section that isn't one of them counts as not chosen. A teacher only sees their own
// class, so for them the choice is `locked` to it.
export function useClassPicker(chosenGrade, chosenSection) {
  const { user } = useApp()
  const fetchTree = useCallback(() => sectionsAPI.tree(), [])
  const { data: tree, loading, error } = useFetch(fetchTree)

  const isTeacher = user?.role === ROLES.TEACHER
  const grade = isTeacher ? user.assigned_grade || '' : chosenGrade
  const sectionNames = sectionsOf(tree, grade).map(s => s.name)
  const section = isTeacher ? user.assigned_section || ''
    : sectionNames.includes(chosenSection) ? chosenSection : ''
  const sectionPlaceholder = loading ? 'Loading...'
    : error ? 'Could not load sections'
    : sectionNames.length === 0 ? `No sections in ${grade}`
    : 'Select a section'

  return {
    locked: isTeacher,
    gradeLevels: tree?.length ? gradeLevelsOf(tree) : GRADE_LEVELS,
    sectionNames, sectionPlaceholder, grade, section,
    // Why nothing can be filed yet, if so
    problem: section ? null : isTeacher ? NO_CLASS : 'Please choose a section.',
  }
}
