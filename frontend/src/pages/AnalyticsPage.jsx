import { useState, useCallback, useMemo } from 'react'
import { GRADE_LEVELS } from '../data/constants'
import { Card, StatCard, Badge, Btn, FormGroup, StatusBanner, EmptyState, PageHeader } from '../components/ui/index'
import ChartCanvas, { CHART_COLORS, barEndLabels, lineEndLabel, legendGap } from '../components/ui/Chart'
import { analyticsAPI } from '../utils/api'
import { useFetch } from '../utils/useFetch'
import { PASSING_GRADE } from '../utils/format'
import { useRecordOptions, withExtras } from '../utils/useRecordOptions'

const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4']
const QUARTER_LABELS = ['Quarter 1', 'Quarter 2', 'Quarter 3', 'Quarter 4']
const ALL_SUBJECTS = ''   // the trend chart's default: the mean over every subject
const BAR_ROW_HEIGHT = 30
const show = (n) => (n === null || n === undefined ? '—' : n)

// A horizontal bar chart of one value per category, 0 to 100, with each value written at its bar's end
function Bars({ rows, format, label }) {
  const data = useMemo(() => ({
    labels: rows.map(r => r.name),
    datasets: [{
      data: rows.map(r => r.value),
      backgroundColor: CHART_COLORS.accent, hoverBackgroundColor: '#1C5CAB',
      maxBarThickness: 18, borderRadius: 4, borderSkipped: 'start',
    }],
  }), [rows])
  const options = useMemo(() => ({
    indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
    layout: { padding: { right: 44 } },
    plugins: { legend: { display: false }, tooltip: { displayColors: false, callbacks: { label: item => format(item.parsed.x) } } },
    scales: {
      x: { min: 0, max: 100, grid: { color: CHART_COLORS.grid }, border: { display: false }, ticks: { stepSize: 25 } },
      y: { grid: { display: false }, border: { color: CHART_COLORS.grid }, ticks: { color: CHART_COLORS.label } },
    },
  }), [format])
  const plugins = useMemo(() => [barEndLabels(format)], [format])
  if (rows.length === 0) return <div className="text-muted" style={{ fontSize: 12, padding: '12px 0' }}>No grades for the selected filters.</div>
  return <ChartCanvas type="bar" data={data} options={options} plugins={plugins} height={rows.length * BAR_ROW_HEIGHT + 36} label={label}/>
}

// Mean grade per quarter. One line is the subject of the chart; the others stay grey behind it.
function TrendChart({ subjects, periodMeans, highlight }) {
  const withQuarters = useMemo(() => subjects.filter(s => QUARTERS.filter(q => s.means[q] !== null).length >= 2), [subjects])
  const chosen = withQuarters.find(s => s.subject === highlight)
  const data = useMemo(() => {
    const context = withQuarters.filter(s => s !== chosen).map(s => ({
      label: s.subject, data: QUARTERS.map(q => s.means[q]),
      borderColor: CHART_COLORS.context, borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 3, pointHitRadius: 12, spanGaps: true,
    }))
    const main = {
      label: chosen ? chosen.subject : 'All subjects',
      data: QUARTERS.map(q => (chosen ? chosen.means[q] : periodMeans?.[q] ?? null)),
      borderColor: CHART_COLORS.accent, backgroundColor: CHART_COLORS.accent, borderWidth: 2,
      pointRadius: 4, pointHoverRadius: 6, pointBorderColor: CHART_COLORS.surface, pointBorderWidth: 2, pointHitRadius: 14, spanGaps: true,
    }
    return { labels: QUARTER_LABELS, datasets: [...context, main] }   // drawn last, so it sits on top
  }, [withQuarters, chosen, periodMeans])
  const mainIndex = data.datasets.length - 1
  const options = useMemo(() => ({
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: 'index', intersect: false },   // one tooltip lists every subject at that quarter
    layout: { padding: { right: 36 } },
    plugins: {
      legend: {
        position: 'top', align: 'start',
        labels: {
          usePointStyle: true, pointStyle: 'line', color: CHART_COLORS.label,
          // one entry for the highlighted line and one standing for all the grey ones
          generateLabels: chart => [
            { text: chart.data.datasets[mainIndex].label, strokeStyle: CHART_COLORS.accent, lineWidth: 2, pointStyle: 'line', fontColor: CHART_COLORS.label },
            ...(mainIndex > 0 ? [{ text: 'Each subject', strokeStyle: CHART_COLORS.context, lineWidth: 2, pointStyle: 'line', fontColor: CHART_COLORS.label }] : []),
          ],
        },
        onClick: () => {},
      },
      tooltip: { itemSort: (a, b) => (b.datasetIndex === mainIndex) - (a.datasetIndex === mainIndex) || b.parsed.y - a.parsed.y },
    },
    scales: {
      x: { grid: { display: false }, border: { color: CHART_COLORS.grid }, ticks: { color: CHART_COLORS.label } },
      y: { suggestedMin: 70, suggestedMax: 100, grid: { color: CHART_COLORS.grid }, border: { display: false } },
    },
  }), [mainIndex])
  const plugins = useMemo(() => [lineEndLabel(mainIndex), legendGap], [mainIndex])
  const hasPoints = data.datasets[mainIndex].data.some(v => v !== null)
  if (!hasPoints) return <div className="text-muted" style={{ fontSize: 12, padding: '12px 0' }}>No quarterly grades for the selected filters.</div>
  return <ChartCanvas type="line" data={data} options={options} plugins={plugins} height={280} label="Mean grade per quarter"/>
}

// The figures behind the charts, subject by subject; the most failing grades come first
function SubjectTable({ subjects }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table>
        <thead>
          <tr>
            <th>Subject</th>
            {QUARTERS.map((q, i) => <th key={q} className="center">Q{i + 1}</th>)}
            <th className="center">Final</th><th className="center">Pass rate</th><th className="center">Failing final ratings</th>
          </tr>
        </thead>
        <tbody>
          {subjects.map(s => (
            <tr key={s.subject}>
              <td className="col-name">{s.subject}</td>
              {QUARTERS.map(q => <td key={q} className="center">{show(s.means[q])}</td>)}
              <td className="center" style={{ fontWeight: 700, color: 'var(--text)' }}>{show(s.means.final)}</td>
              <td className="center">{s.pass_rate === null ? '—' : `${s.pass_rate}%`}</td>
              <td className="center">
                {s.failed > 0 ? <Badge type="b-rose">{s.failed} of {s.graded}</Badge> : s.graded > 0 ? `0 of ${s.graded}` : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function InterventionFlags({ flags }) {
  return (
    <Card title="Intervention flags" meta={`Raised when a subject's class mean falls below ${PASSING_GRADE}`}>
      {flags.length === 0
        ? <div style={{ color: 'var(--green)', fontSize: 12, padding: '12px 0' }}>✓ No intervention flags. Every subject's class mean is {PASSING_GRADE} or higher.</div>
        : flags.map((f, i) => (
          <div key={i} className="flag-row">
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--rose)' }}>{f.subject} — {f.grade_level}</div>
              <div className="text-muted" style={{ fontSize: 11 }}>Class mean {f.mean}, below the passing grade of {PASSING_GRADE}</div>
            </div>
            <Badge type="b-rose">Active</Badge>
          </div>
        ))}
    </Card>
  )
}

const asMean = (n) => `${n}`
const asPercent = (n) => `${n}%`

export default function AnalyticsPage() {
  const [filters, setFilters] = useState({ school_year: '', grade: '', section: '' })
  const [highlight, setHighlight] = useState(ALL_SUBJECTS)
  const options = useRecordOptions()

  const fetchAnalytics = useCallback(
    () => analyticsAPI.dashboard(Object.fromEntries(Object.entries(filters).filter(([, v]) => v))),
    [filters],
  )
  const { data, loading, error, refetch } = useFetch(fetchAnalytics)
  const setFilter = (key, value) => setFilters(f => ({ ...f, [key]: value }))

  const subjects = useMemo(() => data?.subjects || [], [data])
  const flags    = data?.intervention_flags || []
  const totalRec = data?.total_records || 0
  const graded   = subjects.reduce((sum, s) => sum + s.graded, 0)
  const failed   = subjects.reduce((sum, s) => sum + s.failed, 0)

  const meanRows = useMemo(() => subjects.filter(s => s.means.final !== null)
    .map(s => ({ name: s.subject, value: s.means.final })).sort((a, b) => b.value - a.value), [subjects])
  const passRows = useMemo(() => subjects.filter(s => s.pass_rate !== null)
    .map(s => ({ name: s.subject, value: s.pass_rate })).sort((a, b) => a.value - b.value), [subjects])
  const gradeRows = useMemo(() => Object.entries(data?.pass_rates || {})
    .map(([name, value]) => ({ name, value })).sort((a, b) => a.name.localeCompare(b.name)), [data])
  const scope = [filters.school_year, filters.grade, filters.section].filter(Boolean).join(' — ') || 'All records'

  return (
    <div>
      <PageHeader title="Grade Analytics" sub="Blank and unreadable grades are left out of every figure."/>
      <StatusBanner error={error} onRetry={refetch}/>
      <Card>
        <div className="filter-bar" style={{ marginBottom: 0, alignItems: 'flex-end' }}>
          <FormGroup label="School year">
            <select className="fld fld-auto" value={filters.school_year} onChange={e => setFilter('school_year', e.target.value)}>
              <option value="">All years</option>
              {options.school_years.map(y => <option key={y}>{y}</option>)}
            </select>
          </FormGroup>
          <FormGroup label="Grade level">
            <select className="fld fld-auto" value={filters.grade} onChange={e => setFilter('grade', e.target.value)}>
              <option value="">All grades</option>
              {withExtras(GRADE_LEVELS, options.grade_levels).map(g => <option key={g}>{g}</option>)}
            </select>
          </FormGroup>
          <FormGroup label="Section">
            <select className="fld fld-auto" value={filters.section} onChange={e => setFilter('section', e.target.value)}>
              <option value="">All sections</option>
              {options.sections.map(s => <option key={s}>{s}</option>)}
            </select>
          </FormGroup>
          <div className="form-group"><Btn size="sm" onClick={() => setFilters({ school_year: '', grade: '', section: '' })}>Clear</Btn></div>
        </div>
      </Card>

      {loading ? <StatusBanner loading/> : totalRec === 0 ? (
        <Card>
          <EmptyState icon="📊">
            {error ? 'Could not load analytics.' : 'No records for the selected filters. Upload or fill out Form 137 records to see analytics here.'}
          </EmptyState>
        </Card>
      ) : (
        <>
          <div className="g4">
            <StatCard value={totalRec.toLocaleString()} label="Records analysed" color="blue"/>
            <StatCard value={show(data?.period_means?.final)} label="Mean final rating" color="green"/>
            <StatCard value={graded ? `${((graded - failed) / graded * 100).toFixed(1)}%` : '—'} label="Final ratings that pass" color="amber"/>
            <StatCard value={failed.toLocaleString()} label="Failing final ratings" color="rose"/>
          </div>

          <div className="g2">
            <Card title="Class mean by subject" meta={`Final rating — ${scope}`}>
              <Bars rows={meanRows} format={asMean} label="Class mean final rating by subject"/>
            </Card>
            <Card title="Trend across grading periods" meta="Mean grade per quarter"
              action={
                <select className="fld fld-auto" value={highlight} onChange={e => setHighlight(e.target.value)} aria-label="Subject to highlight">
                  <option value={ALL_SUBJECTS}>All subjects</option>
                  {subjects.map(s => <option key={s.subject}>{s.subject}</option>)}
                </select>
              }>
              <TrendChart subjects={subjects} periodMeans={data?.period_means} highlight={highlight}/>
            </Card>
            <Card title="Pass rate by subject" meta={`Share of final ratings at ${PASSING_GRADE} or higher — lowest first`}>
              <Bars rows={passRows} format={asPercent} label="Pass rate by subject"/>
            </Card>
            <Card title="Pass rate by grade level" meta="Share of records whose general average passes">
              <Bars rows={gradeRows} format={asPercent} label="Pass rate by grade level"/>
            </Card>
          </div>

          <Card title="Subjects by grading period" meta="Class means, with the most failing final ratings first">
            <SubjectTable subjects={subjects}/>
          </Card>
          <InterventionFlags flags={flags}/>
        </>
      )}
    </div>
  )
}
