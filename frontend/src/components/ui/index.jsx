// Small presentational building blocks shared by every page. Styles live in styles/components.css.

export function Badge({ type = 'b-grey', children }) {
  return <span className={`badge ${type}`}>{children}</span>
}

export function Btn({ variant = 'secondary', size = '', onClick, children, style, disabled }) {
  return (
    <button className={`btn btn-${variant}${size ? ` btn-${size}` : ''}`} onClick={onClick} style={style} disabled={disabled}>
      {children}
    </button>
  )
}

const ICONS = {
  pencil: <><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></>,
  trash:  <><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></>,
}

// Icon-only button; `label` is its tooltip and what screen readers announce
export function IconBtn({ icon, label, variant = 'secondary', onClick }) {
  return (
    <button className={`btn btn-${variant} btn-icon`} onClick={onClick} title={label} aria-label={label}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{ICONS[icon]}</svg>
    </button>
  )
}

export function Card({ title, meta, action, children, style, className = '' }) {
  return (
    <div className={`card ${className}`} style={style}>
      {(title || action) && (
        <div className="card-hd">
          <span className="card-title">{title}</span>
          {meta && <span className="card-meta">{meta}</span>}
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  )
}

export function PageHeader({ title, sub }) {
  return (
    <>
      <div className="page-title">{title}</div>
      {sub && <div className="page-sub">{sub}</div>}
    </>
  )
}

export function StatCard({ value, label, color = 'blue' }) {
  return (
    <div className={`stat ${color}`}>
      <div className="stat-val">{value}</div>
      <div className="stat-lbl">{label}</div>
    </div>
  )
}

export function Alert({ type = 'blue', children, style }) {
  return <div className={`alert alert-${type}`} style={style}>{children}</div>
}

// Inline message box for form errors / success (type: 'error' | 'success')
export function Notice({ type = 'error', children }) {
  if (!children) return null
  return <div className={`notice notice-${type}`}>{children}</div>
}

export function FormGroup({ label, children }) {
  return <div className="form-group"><label>{label}</label>{children}</div>
}

export function InfoRow({ label, children }) {
  return <div className="info-row"><div className="info-lbl">{label}</div><div className="info-val">{children}</div></div>
}

export function ConfBar({ pct, cls = 'cf-h' }) {
  return <div className="conf-bar"><div className={`conf-fill ${cls}`} style={{ width: `${pct}%` }}/></div>
}

export function BarRow({ name, pct, val, cls }) {
  return (
    <div className="bar-row">
      <div className="bar-nm">{name}</div>
      <div className="bar-track">
        <div className={`bar-fill ${cls}`} style={{ width: `${Math.min(pct, 100)}%` }}><span>{val}</span></div>
      </div>
    </div>
  )
}

export function EmptyState({ icon, children, action }) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-icon">{icon}</div>}
      {children}
      {action && <div className="empty-action">{action}</div>}
    </div>
  )
}

export function SearchInput({ value, onChange, onEnter, placeholder, style }) {
  return (
    <div className="search-bar" style={style}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="search-icon">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && onEnter?.()}
        placeholder={placeholder}
      />
    </div>
  )
}

const REMARKS_BADGES = { Promoted: 'b-green', Retained: 'b-amber', Incomplete: 'b-blue' }
// A record with grades still missing can't be decided; it is shown the way the school words it
const REMARKS_LABELS = { Incomplete: 'Incomplete / For Verification' }

export function RemarksBadge({ remarks }) {
  if (!remarks) return <Badge type="b-grey">Pending</Badge>
  return <Badge type={REMARKS_BADGES[remarks] || 'b-grey'}>{REMARKS_LABELS[remarks] || remarks}</Badge>
}

export function Pager({ page, total, size = 20, onChange }) {
  const pages = Math.ceil(total / size) || 1
  if (pages <= 1) return null
  return (
    <div className="pager">
      <div className="pager-btn" onClick={() => page > 1 && onChange(page - 1)}>Prev</div>
      {Array.from({ length: Math.min(pages, 7) }, (_, i) => i + 1).map(p => (
        <div key={p} className={`pager-btn${p === page ? ' active' : ''}`} onClick={() => onChange(p)}>{p}</div>
      ))}
      {pages > 7 && <>
        <div className="pager-btn">...</div>
        <div className="pager-btn" onClick={() => onChange(pages)}>{pages}</div>
      </>}
      <div className="pager-btn" onClick={() => page < pages && onChange(page + 1)}>Next</div>
    </div>
  )
}

// Loading spinner, "backend offline" banner (error === 'offline'), or error box with Retry.
export function StatusBanner({ loading, error, onRetry }) {
  if (loading) {
    return (
      <div className="empty-state">
        <div className="loading-icon">⟳</div>
        <div>Loading...</div>
      </div>
    )
  }
  if (error === 'offline') {
    return (
      <div className="banner banner-offline">
        <span className="banner-icon">⚠</span>
        <div style={{ flex: 1 }}>
          <strong>Can't reach the server.</strong> Check that OCRIS is running, then retry.
        </div>
        {onRetry && <button className="banner-retry" onClick={onRetry}>Retry</button>}
      </div>
    )
  }
  if (error) {
    return (
      <div className="banner banner-error">
        <strong>Error:</strong> {error}
        {onRetry && <button className="banner-retry" onClick={onRetry}>Retry</button>}
      </div>
    )
  }
  return null
}
