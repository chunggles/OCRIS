// Chart.js charts for the analytics pages. Only the chart types in use are registered, which
// keeps the rest of the library out of the bundle.
import { useEffect, useRef } from 'react'
import {
  Chart, BarController, BarElement, LineController, LineElement, PointElement,
  CategoryScale, LinearScale, Tooltip, Legend,
} from 'chart.js'

Chart.register(BarController, BarElement, LineController, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend)

// Chart colours. A canvas can't read CSS variables, so the app's ink and line colours are repeated
// here. The accent is stronger than the app's own blue, which is too grey to carry data.
export const CHART_COLORS = {
  accent:  '#2A78D6',   // the series the chart is about
  context: '#C3C7D1',   // every other series, kept in the background
  ink:     '#1E2636',   // values
  label:   '#4A5568',   // category names
  muted:   '#8A94A8',   // axis ticks
  grid:    '#EDF0F7',
  surface: '#FFFFFF',
}
const FONT = "'Inter','Segoe UI',system-ui,sans-serif"
Chart.defaults.font.family = FONT
Chart.defaults.font.size = 11
Chart.defaults.color = CHART_COLORS.muted

// Draws each value of the first dataset at the end of its bar (horizontal bar charts)
export const barEndLabels = (format = String) => ({
  id: 'barEndLabels',
  afterDatasetsDraw(chart) {
    const { ctx } = chart
    ctx.save()
    ctx.fillStyle = CHART_COLORS.ink
    ctx.font = `600 11px ${FONT}`
    ctx.textBaseline = 'middle'
    chart.getDatasetMeta(0).data.forEach((bar, i) => {
      const value = chart.data.datasets[0].data[i]
      if (value !== null && value !== undefined) ctx.fillText(format(value), bar.x + 6, bar.y)
    })
    ctx.restore()
  },
})

// Leaves a gap under the legend, which Chart.js otherwise sets hard against the plot
export const legendGap = {
  id: 'legendGap',
  beforeInit(chart) {
    const fit = chart.legend.fit
    chart.legend.fit = function fitWithGap() { fit.call(this); this.height += 10 }
  },
}

// Draws the last value of one dataset beside the end of its line
export const lineEndLabel = (datasetIndex, format = String) => ({
  id: 'lineEndLabel',
  afterDatasetsDraw(chart) {
    const points = chart.getDatasetMeta(datasetIndex)?.data || []
    const values = chart.data.datasets[datasetIndex]?.data || []
    let last = values.length - 1
    while (last >= 0 && (values[last] === null || values[last] === undefined)) last--
    if (last < 0 || !points[last]) return
    const { ctx } = chart
    ctx.save()
    ctx.fillStyle = CHART_COLORS.ink
    ctx.font = `600 11px ${FONT}`
    ctx.textBaseline = 'middle'
    ctx.fillText(format(values[last]), points[last].x + 9, points[last].y)
    ctx.restore()
  },
})

// `data`, `options` and `plugins` must keep the same identity between renders unless the chart
// should be redrawn (build them with useMemo). `label` describes the chart to screen readers.
export default function ChartCanvas({ type, data, options, plugins, height = 240, label }) {
  const canvas = useRef(null)
  useEffect(() => {
    const chart = new Chart(canvas.current, { type, data, options, plugins })
    return () => chart.destroy()
  }, [type, data, options, plugins])
  return (
    <div style={{ position: 'relative', height }}>
      <canvas ref={canvas} role="img" aria-label={label}/>
    </div>
  )
}
