
import { useEffect, useState } from 'react'
import {
  ArrowUpRight,
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, getError, money, rowsFrom, titleCase } from '../lib/api'
import { Alert, Loading, PageHeader, StatusPill } from '../components/Shared'

const Stat = ({
  label,
  value,
  sub,
  icon: Icon,
  tint = 'teal',
}: any) => (
  <div className="panel p-5">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs font-semibold text-slate-500">{label}</p>
        <p className="mt-2 font-display text-[27px] font-extrabold tracking-tight text-ink">
          {value}
        </p>
        <p className="mt-1 text-[11px] text-slate-400">{sub}</p>
      </div>
      <div
        className={`rounded-xl p-3 ${
          tint === 'rose'
            ? 'bg-rose-50 text-rose-600'
            : tint === 'amber'
              ? 'bg-amber-50 text-amber-600'
              : tint === 'blue'
                ? 'bg-blue-50 text-blue-600'
                : 'bg-teal/10 text-teal'
        }`}
      >
        <Icon size={19} />
      </div>
    </div>
  </div>
)

export default function Dashboard() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    setError('')

    try {
      const [health, quotes, underwriting, anomalies, renewals] =
        await Promise.allSettled([
          api.get('/api/health'),
          api.get('/api/quotes?limit=100'),
          api.get('/api/underwriting/summary'),
          api.get('/api/anomalies/summary'),
          api.get('/api/renewals'),
        ])

      setData({
        health: health.status === 'fulfilled' ? health.value.data : null,
        quotes:
          quotes.status === 'fulfilled'
            ? rowsFrom(quotes.value.data, 'quotes')
            : [],
        underwriting:
          underwriting.status === 'fulfilled'
            ? underwriting.value.data
            : null,
        anomalies:
          anomalies.status === 'fulfilled'
            ? anomalies.value.data
            : null,
        renewals:
          renewals.status === 'fulfilled'
            ? rowsFrom(renewals.value.data, 'renewals')
            : [],
      })

      const failed = [
        health,
        quotes,
        underwriting,
        anomalies,
        renewals,
      ].filter((item) => item.status === 'rejected')

      if (failed.length) {
        setError(
          'Some dashboard panels could not load. Check API availability and the relevant endpoint.'
        )
      }
    } catch (e) {
      setError(getError(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) return <Loading label="Loading underwriting overview…" />

  const q = data?.quotes || []

  const statusCounts = q.reduce(
    (acc: any, row: any) => {
      const status = row.quote_status || 'UNKNOWN'
      acc[status] = (acc[status] || 0) + 1
      return acc
    },
    {}
  )

  const chart = Object.entries(statusCounts).map(([name, value]) => ({
    name: titleCase(name),
    quotes: value,
  }))

  const anomalyCount = data?.anomalies?.total_anomalies ?? '—'
  const mediumAnomalies = data?.anomalies?.medium_severity ?? 0
  const highAnomalies = data?.anomalies?.high_severity ?? 0

  const healthStatus = data?.health?.status || 'Unavailable'
  const databaseHealthy =
    String(healthStatus).toLowerCase() === 'healthy' ||
    String(healthStatus).toLowerCase() === 'ok'

  const finalDecisions =
    data?.underwriting?.totals?.final_decisions ?? 0

  return (
    <>
      <PageHeader
        eyebrow="Portfolio pulse"
        title="Underwriting overview"
        subtitle="A consolidated view of submissions, decisions, renewals and control exceptions."
        action={
          <button className="btn-secondary" onClick={load}>
            <RefreshCw size={15} />
            Refresh data
          </button>
        }
      />

      {error && <Alert kind="info">{error}</Alert>}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Quotes loaded"
          value={q.length}
          sub="Latest records returned by API"
          icon={FileText}
        />
        <Stat
          label="Underwriting decisions"
          value={data?.underwriting?.totals?.total_decisions ?? '—'}
          sub="Automated and human decisions"
          icon={ClipboardCheck}
          tint="blue"
        />
        <Stat
          label="Renewal records"
          value={data?.renewals?.length ?? '—'}
          sub="Current renewal portfolio"
          icon={RefreshCw}
          tint="amber"
        />
        <Stat
          label="Detected anomalies"
          value={anomalyCount}
          sub={`${highAnomalies} high severity`}
          icon={AlertTriangle}
          tint="rose"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
        <section className="panel p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="font-display text-base font-bold">
                Quote status distribution
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                Based on latest quote records returned by the API
              </p>
            </div>
            <span className="rounded-lg bg-slate-50 px-2.5 py-1 text-[10px] font-bold text-slate-500">
              LIVE DATA
            </span>
          </div>

          {chart.length ? (
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={chart}
                  margin={{ top: 10, right: 10, left: -18, bottom: 0 }}
                >
                  <defs>
                    <linearGradient
                      id="quoteFill"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop offset="0%" stopColor="#0e9384" stopOpacity={0.22} />
                      <stop offset="95%" stopColor="#0e9384" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#edf1f6" vertical={false} />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: '#8994a7' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 11, fill: '#8994a7' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="quotes"
                    stroke="#0e9384"
                    strokeWidth={2.5}
                    fill="url(#quoteFill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="py-16 text-center text-sm text-slate-400">
              No quote data returned yet.
            </div>
          )}
        </section>

        {/* Admin Control Centre */}
        <section className="panel p-5 sm:p-6">
          <div className="mb-5">
            <h2 className="font-display text-base font-bold">
              Control centre
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              System and governance signals
            </p>
          </div>

          <div className="space-y-4">
            {/* Database connection */}
            <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
              <div
                className={`rounded-lg p-2 ${
                  databaseHealthy
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-rose-100 text-rose-700'
                }`}
              >
                {databaseHealthy ? (
                  <CheckCircle2 size={17} />
                ) : (
                  <AlertTriangle size={17} />
                )}
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold">Database connection</p>
                <p className="text-xs text-slate-500">
                  {data?.health?.database || 'Database status unavailable'}
                </p>
              </div>

              <StatusPill
                value={databaseHealthy ? 'HEALTHY' : 'UNAVAILABLE'}
              />
            </div>

            {/* Anomaly monitoring */}
            <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
              <div className="rounded-lg bg-rose-100 p-2 text-rose-700">
                <AlertTriangle size={17} />
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold">Anomaly monitoring</p>
                <p className="text-xs text-slate-500">
                  {mediumAnomalies} medium · {highAnomalies} high
                </p>
              </div>

              {Number(anomalyCount) > 0 ? (
                <a
                  href="/anomalies"
                  className="rounded-lg bg-slate-100 px-3 py-1.5 text-[10px] font-bold text-slate-600 transition hover:bg-rose-50 hover:text-rose-700"
                >
                  Review
                </a>
              ) : (
                <StatusPill value="CLEAR" />
              )}
            </div>

            {/* Decision traceability */}
            <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
              <div className="rounded-lg bg-blue-100 p-2 text-blue-700">
                <ShieldCheck size={17} />
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold">Decision traceability</p>
                <p className="text-xs text-slate-500">
                  {finalDecisions} final decisions recorded
                </p>
              </div>

              <StatusPill value="Enabled" />
            </div>
          </div>
        </section>
      </div>

      <section className="panel mt-5 p-5 sm:p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="font-display text-base font-bold">
              Recent quote activity
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Most recent submissions from the API
            </p>
          </div>
          <a href="/quotes" className="text-xs font-bold text-teal">
            View quotes <ArrowUpRight size={13} className="inline" />
          </a>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-head px-3 py-3">Quote ID</th>
                <th className="table-head px-3 py-3">Applicant</th>
                <th className="table-head px-3 py-3">Status</th>
                <th className="table-head px-3 py-3">Premium</th>
                <th className="table-head px-3 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {q.slice(0, 6).map((r: any) => (
                <tr key={r.quote_id}>
                  <td className="table-cell font-semibold text-ink">
                    {r.quote_id}
                  </td>
                  <td className="table-cell">{r.applicant_id}</td>
                  <td className="table-cell">
                    <StatusPill value={r.quote_status} />
                  </td>
                  <td className="table-cell">
                    {money(r.calculated_premium, r.currency || 'INR')}
                  </td>
                  <td className="table-cell">
                    {r.created_at
                      ? new Date(r.created_at).toLocaleDateString('en-IN')
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {!q.length && (
            <p className="py-8 text-center text-sm text-slate-400">
              No quotes available.
            </p>
          )}
        </div>
      </section>
    </>
  )
}
