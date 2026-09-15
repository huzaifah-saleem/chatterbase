// Dashboards: named collections of pinned charts. Parity port with a
// grid-card list on the left, selected dashboard's charts on the right.
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import ChartCard from '../components/ChartCard'

export default function DashboardsView() {
  const [dashboards, setDashboards] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [active, setActive] = useState(null)

  const loadList = () => api.listDashboards().then((d) => setDashboards(d.dashboards || []))
  useEffect(() => { loadList() }, [])
  useEffect(() => { if (activeId) api.getDashboard(activeId).then(setActive) }, [activeId])

  const create = async () => {
    const name = prompt('Dashboard name:')
    if (!name) return
    const d = await api.createDashboard(name)
    await loadList()
    setActiveId(d.id)
  }
  const remove = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this dashboard and everything pinned to it?')) return
    await api.deleteDashboard(id)
    if (id === activeId) { setActiveId(null); setActive(null) }
    loadList()
  }
  const unpin = async (chartId) => {
    await api.unpinChart(activeId, chartId)
    setActive(await api.getDashboard(activeId))
  }
  const changeType = async (chartId, type) => {
    await api.updateChartType(activeId, chartId, type)
  }

  return (
    <div className="flex-1 flex min-h-0">
      <aside className="w-64 shrink-0 border-r border-edge flex flex-col">
        <div className="p-3">
          <button onClick={create} className="w-full py-2.5 rounded-lg grad text-white text-sm font-semibold hover:opacity-90 transition">+ New Dashboard</button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2 flex flex-col gap-1">
          {dashboards.map((d) => (
            <div
              key={d.id}
              onClick={() => setActiveId(d.id)}
              className={`group flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer transition
                ${d.id === activeId ? 'bg-accent/15 text-accent-hot' : 'text-ink-dim hover:bg-panel hover:text-ink'}`}
            >
              <span className="truncate">{d.name} <span className="text-ink-faint">({d.chart_count})</span></span>
              <button onClick={(e) => remove(d.id, e)} className="opacity-0 group-hover:opacity-100 text-ink-faint hover:text-bad transition shrink-0">&times;</button>
            </div>
          ))}
          {dashboards.length === 0 && <div className="px-3 py-2 text-xs text-ink-faint">No dashboards yet</div>}
        </div>
      </aside>

      <div className="flex-1 overflow-y-auto p-6">
        {!active ? (
          <div className="h-full flex items-center justify-center text-ink-faint text-sm">Select or create a dashboard</div>
        ) : (
          <>
            <h2 className="text-lg font-semibold text-ink mb-4">📊 {active.name}</h2>
            {active.charts?.length ? (
              <div className="grid grid-cols-2 gap-4">
                {active.charts.map((c) => (
                  <ChartCard key={c.id} chart={c} onTypeChange={(t) => changeType(c.id, t)} onUnpin={() => unpin(c.id)} />
                ))}
              </div>
            ) : (
              <div className="text-sm text-ink-faint">No charts pinned yet. Pin one from a chat or agent result.</div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
