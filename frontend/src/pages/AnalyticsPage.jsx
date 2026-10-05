import { useState, useCallback } from 'react'
import { GRADE_LEVELS } from '../data/constants'
import { Card, StatCard, Badge, Btn, BarRow, FormGroup, StatusBanner, EmptyState, PageHeader } from '../components/ui/index'
import { analyticsAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { PASSING_GRADE } from '../utils/format'
import { useRecordOptions, withExtras } from '../utils/useRecordOptions'

const meanColor = (mean) => (mean >= 85 ? 'bf-blue' : mean >= PASSING_GRADE ? 'bf-amber' : 'bf-rose')
const rateColor = (rate) => (rate >= 90 ? 'bf-green' : rate >= 80 ? 'bf-amber' : 'bf-rose')

const toBars = (obj, toVal, toColor) => Object.entries(obj || {})
  .sort((a, b) => b[1] - a[1])
  .map(([name, n]) => ({ name, n, pct: Math.min(n, 100), val: toVal(n), cls: toColor(n) }))

const average = (nums) => nums.reduce((sum, n) => sum + n, 0) / nums.length

function BarList({ bars, emptyText }) {
  if (bars.length === 0) return <div className="text-muted" style={{ fontSize: 12, padding: '12px 0' }}>{emptyText}</div>
  return <div className="bar-list">{bars.map(b => <BarRow key={b.name} {...b}/>)}</div>
}

function InterventionFlags({ flags }) {
  return (
    <Card title="Intervention flags" meta={`Auto-generated when class mean falls below ${PASSING_GRADE}`}>
      {flags.length === 0
        ? <div style={{ color: 'var(--green)', fontSize: 12, padding: '12px 0' }}>✓ No intervention flags. All subject means are at or above {PASSING_GRADE}%.</div>
        : flags.map((f, i) => (
          <div key={i} className="flag-row">
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--rose)' }}>{f.subject} — {f.grade_level}</div>
              <div className="text-muted" style={{ fontSize: 11 }}>Class mean: {f.mean} — Below {PASSING_GRADE}% threshold</div>
            </div>
            <Badge type="b-rose">Active</Badge>
          </div>
        ))}
    </Card>
  )
}

export default function AnalyticsPage() {
  const [schoolYear, setSchoolYear] = useState('')
  const [grade,      setGrade]      = useState('')
  const options = useRecordOptions()

  const fetchAnalytics = useCallback(() => analyticsAPI.dashboard({
    ...(schoolYear && { school_year: schoolYear }),
    ...(grade && { grade }),
  }), [schoolYear, grade])
  const { data, loading, error, refetch } = useFetch(fetchAnalytics)

  const subjectBars = toBars(data?.subject_means, n => `${n}`, meanColor)
  const passBars    = toBars(data?.pass_rates, n => `${n}%`, rateColor)
  const flags       = data?.intervention_flags || []
  const totalRec    = data?.total_records || 0
  const overallAvg  = subjectBars.length ? average(subjectBars.map(b => b.n)).toFixed(1) : '—'
  const avgPass     = passBars.length ? `${average(passBars.map(b => b.n)).toFixed(1)}%` : '—'

  return (
    <div>
      <PageHeader title="Grade Analytics" sub="Blank (N/A) grades are excluded."/>
      <StatusBanner error={error} onRetry={refetch}/>
      <Card>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <FormGroup label="School year">
            <select className="fld fld-auto" value={schoolYear} onChange={e => setSchoolYear(e.target.value)}>
              <option value="">All years</option>
              {options.school_years.map(y => <option key={y}>{y}</option>)}
            </select>
          </FormGroup>
          <FormGroup label="Grade level">
            <select className="fld fld-auto" value={grade} onChange={e => setGrade(e.target.value)}>
              <option value="">All grades</option>
              {withExtras(GRADE_LEVELS, options.grade_levels).map(g => <option key={g}>{g}</option>)}
            </select>
          </FormGroup>
          <Btn size="sm" onClick={() => { setSchoolYear(''); setGrade('') }}>Clear</Btn>
        </div>
      </Card>

      {loading ? <StatusBanner loading/> : totalRec === 0 ? (
        <Card>
          <EmptyState icon="📊">
            {error ? 'Could not load analytics.' : 'No records yet. Upload Form 137 records to see analytics here.'}
          </EmptyState>
        </Card>
      ) : (
        <>
          <div className="g4">
            <StatCard value={totalRec.toLocaleString()} label="Records analysed"    color="blue"/>
            <StatCard value={overallAvg}                label="School-wide average" color="green"/>
            <StatCard value={flags.length}              label="Intervention flags"  color="rose"/>
            <StatCard value={avgPass}                   label="Overall pass rate"   color="amber"/>
          </div>
          <div className="g2">
            <Card title="Class mean by subject" meta={[schoolYear, grade].filter(Boolean).join(' — ') || 'All records'}>
              <BarList bars={subjectBars} emptyText="No grade data for selected filters."/>
            </Card>
            <Card title="Pass rate by grade level">
              <BarList bars={passBars} emptyText="No pass rate data yet."/>
            </Card>
            <InterventionFlags flags={flags}/>
          </div>
        </>
      )}
    </div>
  )
}
