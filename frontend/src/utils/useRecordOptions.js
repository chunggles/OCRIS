import { useCallback } from 'react'
import { recordsAPI } from './api'
import { useFetch } from './useFetch'

const EMPTY = { grade_levels: [], sections: [], school_years: [] }

// The grade levels, sections and school years that saved records actually use, for filter dropdowns
export function useRecordOptions() {
  const fetchOptions = useCallback(() => recordsAPI.options(), [])
  const { data } = useFetch(fetchOptions)
  return data || EMPTY
}

// Fixed choices first, then any extra values found in the records
export const withExtras = (fixed, extras) => [...fixed, ...extras.filter(v => !fixed.includes(v))]
