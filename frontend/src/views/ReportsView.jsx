// Reports: agent-authored narrative + pinned charts, saved via the
// create_report tool (agent_orchestrator.py). Read-only gallery, mirroring
// DashboardsView.jsx's list-on-left/content-on-right layout - reports are
// authored by an agent, not created here, so there's no "+ New" button.
// Rendering reuses Blocks.jsx exactly - a report's blocks are the same
// {type: text|table|chart} shape chat/task results already use.
import { useEffect, useState } from 'react'
import { FileText, Pencil, Download } from 'lucide-react'
import { api } from '../lib/api'
import { Blocks } from '../components/Blocks'

export default function ReportsView() {
  const [reports, setReports] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [active, setActive] = useState(null)

  const loadList = () => api.listReports().then((d) => setReports(d.reports || []))
  useEffect(() => { loadList() }, [])
  useEffect(() => { if (activeId) api.getReport(activeId).then(setActive) }, [activeId])

  const remove = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this report?')) return
    await api.deleteReport(id)
    if (id === activeId) { setActiveId(null); setActive(null) }
    loadList()
  }
  const rename = async (r, e) => {
    e.stopPropagation()
    const title = prompt('Rename report:', r.title)
    if (!title || title === r.title) return
    try {
      await api.renameReport(r.id, title)
      loadList()
      if (r.id === activeId) setActive(await api.getReport(activeId))
    } catch (err) { alert(err.message) }
  }

  return (
    <div className="flex-1 flex min-h-0">
      <aside className="w-64 shrink-0 border-r border-edge flex flex-col">
        <div className="p-3 text-xs text-ink-faint">Agent-authored reports appear here automatically.</div>
        <div className="flex-1 overflow-y-auto px-2 pb-2 flex flex-col gap-1">
          {reports.map((r) => (
            <div
              key={r.id}
              onClick={() => setActiveId(r.id)}
              className={`group flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer transition
                ${r.id === activeId ? 'bg-accent/15 text-accent' : 'text-ink-dim hover:bg-panel hover:text-ink'}`}
            >
              <span className="truncate">{r.title} <span className="text-ink-faint">({r.chart_count})</span></span>
              <span className="flex items-center gap-1 opacity-60 group-hover:opacity-100 shrink-0">
                <button onClick={(e) => rename(r, e)} className="text-ink-faint hover:text-ink transition"><Pencil size={12} /></button>
                <button onClick={(e) => remove(r.id, e)} className="text-ink-faint hover:text-bad transition">&times;</button>
              </span>
            </div>
          ))}
          {reports.length === 0 && <div className="px-3 py-2 text-xs text-ink-faint">No reports yet</div>}
        </div>
      </aside>

      <div className="flex-1 overflow-y-auto p-6">
        {!active ? (
          <div className="h-full flex items-center justify-center text-ink-faint text-sm">Select a report</div>
        ) : (
          <div className="max-w-3xl">
            <div className="flex items-start justify-between gap-4 mb-5">
              <h2 className="text-lg font-semibold text-ink flex items-center gap-2"><FileText size={18} className="text-ink-faint" />{active.title}</h2>
              <div className="flex gap-2 shrink-0">
                <a href={`/api/reports/${active.id}/export?format=html`} className="text-xs px-3 py-1.5 rounded-lg bg-edge hover:bg-edge-bright text-ink transition flex items-center gap-1.5"><Download size={12} /> HTML</a>
                <a href={`/api/reports/${active.id}/export?format=md`} className="text-xs px-3 py-1.5 rounded-lg bg-edge hover:bg-edge-bright text-ink transition flex items-center gap-1.5"><Download size={12} /> Markdown</a>
              </div>
            </div>
            <Blocks blocks={active.blocks} />
          </div>
        )}
      </div>
    </div>
  )
}
