// Helpers shared by the Upload Form 137 steps

export const pupilName = (form) => `${form.last_name}, ${form.first_name}`

// Coloured count tiles used by the Processing and Extraction steps.
// tiles: [{ value, label, color }] where color is 'green' | 'amber' | 'blue' | 'grey'
export function SummaryTiles({ tiles, size = 'md' }) {
  return (
    <div className={`tiles tiles-${size}`} style={{ gridTemplateColumns: `repeat(${tiles.length}, 1fr)` }}>
      {tiles.map(t => (
        <div key={t.label} className={`tile tile-${t.color}`}>
          <div className="tile-val">{t.value}</div>
          <div className="tile-lbl">{t.label}</div>
        </div>
      ))}
    </div>
  )
}
