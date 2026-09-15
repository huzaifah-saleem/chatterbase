// In-app activity log (observability.py's SQLite event log) + a link to
// the self-hosted Langfuse UI for deep LLM/tool traces, when configured.
import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const KIND_COLOR = {
  run_start: 'text-accent-hot', done: 'text-good', interrupted: 'text-warn',
  chat_message: 'text-accent-hot', tool_call: 'text-ink-dim', resume: 'text-ink-dim',
}

function StatCard({ label, value }) {
  return (
    <div className="card p-4">
      <div className="text-2xl font-semibold text-ink">{value}</div>
      <div className="text-xs text-ink-dim mt-1">{label}</div>
    </div>
  )
}

export default function ActivityView() {
  const [stats, setStats] = useState(null)
  const [events, setEvents] = useState([])
  const [langfuseUrl, setLangfuseUrl] = useState(null)
  const [kindFilter, setKindFilter] = useState('')

  const load = () => {
    api.activityStats().then(setStats).catch(() => {})
    api.activity(kindFilter ? { kind: kindFilter } : {}).then((d) => setEvents(d.events || [])).catch(() => {})
  }
  useEffect(() => { api.config().then((c) => setLangfuseUrl(c.langfuse_url)).catch(() => {}) }, [])
  useEffect(() => {
    load()
    const id = setInterval(load, 10000)
    return () => clearInterval(id)
  }, [kindFilter])

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-4xl mx-auto flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink">Activity</h1>
            <p className="text-sm text-ink-dim mt-1">Runs, tool calls, and errors across every agent - a live event log fed by every graph invoke.</p>
          </div>
          {langfuseUrl && (
            <a href={langfuseUrl} target="_blank" rel="noreferrer" className="text-xs px-3 py-2 rounded-lg grad text-white font-medium hover:opacity-90 transition">
              Open in Langfuse →
            </a>
          )}
        </div>

        {stats && (
          <div className="grid grid-cols-5 gap-3">
            <StatCard label="Total runs" value={stats.total_runs} />
            <StatCard label="Runs today" value={stats.runs_today} />
            <StatCard label="Tool calls" value={stats.tool_calls} />
            <StatCard label="Errors" value={stats.errors} />
            <StatCard label="Avg tool time" value={`${stats.avg_tool_duration_ms}ms`} />
          </div>
        )}

        {!langfuseUrl && (
          <div className="card p-3 text-xs text-ink-faint">
            Langfuse isn't configured (or is unreachable) - showing the in-app activity log only. Deep LLM/tool traces need the Langfuse stack from docker-compose.yml running.
          </div>
        )}

        <div className="card overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-edge">
            <h3 className="text-sm font-semibold text-ink">Recent Events</h3>
            <select className="text-xs bg-panel border border-edge rounded-lg px-2 py-1 text-ink" value={kindFilter} onChange={(e) => setKindFilter(e.target.value)}>
              <option value="">All kinds</option>
              <option value="run_start">run_start</option>
              <option value="tool_call">tool_call</option>
              <option value="chat_message">chat_message</option>
              <option value="resume">resume</option>
              <option value="done">done</option>
              <option value="interrupted">interrupted</option>
            </select>
          </div>
          <div className="max-h-[520px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-panel">
                <tr>
                  <th className="text-left px-4 py-2 text-ink-faint font-medium">Time</th>
                  <th className="text-left px-4 py-2 text-ink-faint font-medium">Kind</th>
                  <th className="text-left px-4 py-2 text-ink-faint font-medium">Label</th>
                  <th className="text-left px-4 py-2 text-ink-faint font-medium">Duration</th>
                  <th className="text-left px-4 py-2 text-ink-faint font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className="border-t border-edge">
                    <td className="px-4 py-2 text-ink-faint whitespace-nowrap">{new Date(e.ts).toLocaleTimeString()}</td>
                    <td className={`px-4 py-2 font-medium ${KIND_COLOR[e.kind] || 'text-ink-dim'}`}>{e.kind}</td>
                    <td className="px-4 py-2 text-ink-dim max-w-md truncate">{e.label}</td>
                    <td className="px-4 py-2 text-ink-faint">{e.duration_ms != null ? `${e.duration_ms}ms` : '—'}</td>
                    <td className={`px-4 py-2 ${e.status === 'error' ? 'text-bad' : 'text-ink-faint'}`}>{e.status}</td>
                  </tr>
                ))}
                {events.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-ink-faint">No activity yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
