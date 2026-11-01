import React, { ReactNode } from 'react'
import { AlertCircle, CheckCircle2, Info, LoaderCircle, Search, X } from 'lucide-react'
import { titleCase } from '../lib/api'

export function PageHeader({ eyebrow, title, subtitle, action }: { eyebrow?: string; title: string; subtitle?: string; action?: ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
    <div><p className="mb-2 text-[11px] font-bold uppercase tracking-[.18em] text-teal">{eyebrow || 'Operations workspace'}</p>
      <h1 className="font-display text-2xl font-extrabold tracking-tight text-ink sm:text-[30px]">{title}</h1>
      {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-slate-500">{subtitle}</p>}</div>
    {action}
  </div>
}

export function StatusPill({ value }: { value: unknown }) {
  const status = String(value ?? 'UNKNOWN').toUpperCase()
  let cls = 'bg-slate-100 text-slate-600'
  if (['APPROVE','APPROVED','ACTIVE','ACCEPTED','CONFIRMED','HEALTHY','LOW','ISSUED'].includes(status)) cls = 'bg-emerald-50 text-emerald-700'
  if (['REFER','REFERRED','PENDING','PENDING_REVIEW','OFFERED','MEDIUM'].includes(status)) cls = 'bg-amber-50 text-amber-700'
  if (['DECLINE','DECLINED','REJECTED','CANCELLED','HIGH','EXPIRED','INELIGIBLE'].includes(status)) cls = 'bg-rose-50 text-rose-700'
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${cls}`}>{titleCase(status)}</span>
}

export function Alert({ kind = 'info', children, onClose }: { kind?: 'info'|'success'|'error'; children: ReactNode; onClose?: () => void }) {
  const Icon = kind === 'error' ? AlertCircle : kind === 'success' ? CheckCircle2 : Info
  const cls = kind === 'error' ? 'border-rose-200 bg-rose-50 text-rose-800' : kind === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-sky-200 bg-sky-50 text-sky-800'
  return <div className={`mb-4 flex items-start gap-2 rounded-xl border px-3.5 py-3 text-sm ${cls}`}><Icon size={17} className="mt-0.5 shrink-0"/><div className="min-w-0 flex-1">{children}</div>{onClose && <button onClick={onClose}><X size={16}/></button>}</div>
}

export function Loading({ label = 'Loading data…' }: { label?: string }) {
  return <div className="flex items-center justify-center gap-2 py-14 text-sm text-slate-500"><LoaderCircle size={18} className="animate-spin"/>{label}</div>
}

export function Empty({ label = 'No records found' }: { label?: string }) {
  return <div className="py-12 text-center text-sm text-slate-400">{label}</div>
}

export function SearchBox({ value, onChange, placeholder = 'Search records…' }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return <div className="relative w-full sm:w-72"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><input className="field pl-9" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}/></div>
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
    <div className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl sm:p-7">
      <div className="mb-5 flex items-center justify-between"><h2 className="font-display text-lg font-bold">{title}</h2><button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X size={18}/></button></div>{children}
    </div>
  </div>
}

function detailLabel(key: string) {
  return key.replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/_/g, ' ').replace(/\b(id)\b/gi, 'ID').replace(/\b(api)\b/gi, 'API').replace(/\b(pdf)\b/gi, 'PDF').replace(/\b(llm)\b/gi, 'LLM').replace(/\s+/g, ' ').trim().replace(/^./, c => c.toUpperCase())
}

function detailValue(key: string, value: unknown): ReactNode {
  if (value === null || value === undefined || value === '') return <span className="text-slate-400">Not provided</span>
  if (typeof value === 'boolean') return <StatusPill value={value ? 'YES' : 'NO'} />
  if (typeof value === 'number') {
    const moneyKey = /premium|amount|price|payment|coverage|limit|sum_insured|deductible|fee/i.test(key)
    return <span className="tabular-nums">{moneyKey ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(value) : new Intl.NumberFormat('en-IN', { maximumFractionDigits: 3 }).format(value)}</span>
  }
  if (typeof value === 'string') {
    if (/^(status|decision|recommendation|severity|risk_category|category)$/i.test(key)) return <StatusPill value={value} />
    if (/(date|_at|timestamp)$/i.test(key) && !Number.isNaN(Date.parse(value))) return <span>{new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: value.includes(':') ? 'short' : undefined })}</span>
    return <span className="break-words">{value}</span>
  }
  if (Array.isArray(value)) {
    if (!value.length) return <span className="text-slate-400">None recorded</span>
    return <div className="mt-2 grid gap-2">{value.map((item, index) => <div key={index} className="rounded-lg border border-slate-200 bg-white p-3">{item && typeof item === 'object' ? <RecordDetails value={item as Record<string, unknown>} compact /> : <div className="text-sm text-slate-700">{String(item)}</div>}</div>)}</div>
  }
  if (typeof value === 'object') return <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50/70 p-3"><RecordDetails value={value as Record<string, unknown>} compact /></div>
  return <span>{String(value)}</span>
}

export function RecordDetails({ value, compact = false }: { value: unknown; compact?: boolean }) {
  if (value === null || value === undefined) return <p className="text-sm text-slate-400">No details available.</p>
  if (Array.isArray(value)) return <div className="grid gap-3">{value.length ? value.map((item, i) => <div key={i} className="rounded-xl border border-slate-200 p-3">{item && typeof item === 'object' ? <RecordDetails value={item} compact /> : <p className="text-sm">{String(item)}</p>}</div>) : <p className="text-sm text-slate-400">No records available.</p>}</div>
  if (typeof value !== 'object') return <p className="text-sm text-slate-700">{String(value)}</p>
  const entries = Object.entries(value as Record<string, unknown>).filter(([, v]) => v !== undefined)
  if (!entries.length) return <p className="text-sm text-slate-400">No details available.</p>
  return <dl className={compact ? 'grid gap-3 sm:grid-cols-2' : 'grid gap-3 sm:grid-cols-2'}>{entries.map(([key, val]) => <div key={key} className={`min-w-0 ${val && typeof val === 'object' ? 'sm:col-span-2' : ''}`}><dt className="mb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">{detailLabel(key)}</dt><dd className="text-sm leading-6 text-slate-700">{detailValue(key, val)}</dd></div>)}</dl>
}

// Backwards-compatible component name: renders readable fields and nested records, never raw JSON.
export function JsonView({ value }: { value: unknown }) {
  return <div className="max-h-[60vh] overflow-y-auto rounded-xl border border-slate-200 bg-white p-4"><RecordDetails value={value} /></div>
}

export function DataTable({ columns, rows, onRowClick }: { columns: { key: string; label: string; render?: (row: any) => ReactNode }[]; rows: any[]; onRowClick?: (row: any) => void }) {
  if (!rows.length) return <Empty/>
  return <div className="overflow-x-auto"><table className="w-full"><thead><tr>{columns.map(c => <th key={c.key} className="table-head px-4 py-3">{c.label}</th>)}</tr></thead>
    <tbody className="divide-y divide-slate-100">{rows.map((row, i) => <tr key={row.id || row.quote_id || row.applicant_id || row.policy_id || row.renewal_id || row.endorsement_id || i} onClick={() => onRowClick?.(row)} className={onRowClick ? 'cursor-pointer transition hover:bg-slate-50' : ''}>{columns.map(c => <td key={c.key} className="table-cell">{c.render ? c.render(row) : String(row[c.key] ?? '—')}</td>)}</tr>)}</tbody></table></div>
}

export function SearchableLookup({
  kind,
  value,
  onChange,
  placeholder = 'Search and select…',
  disabled = false,
  filterBy = '',
  filterKey = 'product_id',
  required = false,
}: {
  kind: string
  value: string
  onChange: (id: string, item?: any) => void
  placeholder?: string
  disabled?: boolean
  filterBy?: string
  filterKey?: string
  required?: boolean
}) {
  const [query, setQuery] = React.useState('')
  const [selectedLabel, setSelectedLabel] = React.useState('')
  const [items, setItems] = React.useState<any[]>([])
  const [open, setOpen] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    if (!open || disabled) return

    const controller = new AbortController()
    setLoading(true)
    setError('')

    import('../lib/api')
      .then(({ api }) =>
        api.get(`/api/lookups/${kind}`, {
          params: {
            q: query,
            ...(filterBy ? { [filterKey]: filterBy } : {}),
          },
          signal: controller.signal,
        })
      )
      .then(r => {
        setItems(Array.isArray(r.data) ? r.data : [])
      })
      .catch(e => {
        if (!controller.signal.aborted) {
          setError(
            e?.response?.data?.detail || 'Could not load options'
          )
          setItems([])
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [kind, query, open, disabled, filterBy, filterKey])

  React.useEffect(() => {
    setSelectedLabel('')
    setQuery('')
    setItems([])
    setError('')
    setOpen(false)
  }, [filterBy])

  return (
    <div className="relative">
      <input
        className="field"
        required={required}
        value={open ? query : value ? (selectedLabel || value) : query}
        disabled={disabled}
        placeholder={placeholder}
        onFocus={() => {
          setOpen(true)
          setQuery('')
        }}
        onChange={e => {
          setQuery(e.target.value)
          setOpen(true)
          onChange('')
        }}
        onBlur={() =>
          window.setTimeout(() => setOpen(false), 160)
        }
        aria-expanded={open}
      />

      {open && (
        <div className="absolute z-30 mt-1 max-h-56 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white p-1 shadow-xl">
          {loading && (
            <p className="px-3 py-2 text-xs text-slate-400">
              Searching…
            </p>
          )}

          {error && (
            <p className="px-3 py-2 text-xs text-rose-600">
              {error}
            </p>
          )}

          {!loading && !error && items.map(item => (
            <button
              type="button"
              key={item.id}
              className="block w-full rounded-lg px-3 py-2 text-left hover:bg-slate-50"
              onMouseDown={e => e.preventDefault()}
              onClick={() => {
                onChange(item.id, item)
                setSelectedLabel(`${item.label} · ${item.id}`)
                setQuery('')
                setOpen(false)
              }}
            >
              <span className="block text-sm font-semibold text-slate-700">
                {item.label}
              </span>
              <span className="block text-[11px] text-slate-400">
                {item.id}{item.detail ? ` · ${item.detail}` : ''}
              </span>
            </button>
          ))}

          {!loading && !error && !items.length && (
            <p className="px-3 py-2 text-xs text-slate-400">
              No matching records
            </p>
          )}
        </div>
      )}
    </div>
  )
}

