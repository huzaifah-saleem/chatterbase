// Dashboards: named collections of pinned charts. List-on-left, selected
// dashboard's charts on the right, arranged in a react-grid-layout grid so
// they can be dragged/resized in edit mode (persisted via PUT .../layout).
// A comments panel toggles in alongside the grid.
import { useEffect, useMemo, useState } from 'react'
import GridLayout, { WidthProvider } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import { LayoutDashboard, Pencil, LayoutGrid, Check, MessageSquare, Trash2, Send } from 'lucide-react'
import { api } from '../lib/api'
import ChartCard from '../components/ChartCard'

const ResponsiveGridLayout = WidthProvider(GridLayout)
const COLS = 12
const ROW_HEIGHT = 28
const DEFAULT_W = 6
const DEFAULT_H = 10

function buildLayout(charts, saved) {
  const savedById = new Map((saved || []).map((l) => [l.i, l]))
  return charts.map((c, idx) => {
    const existing = savedById.get(c.id)
    if (existing) return { ...existing, i: c.id }
    return { i: c.id, x: (idx % 2) * DEFAULT_W, y: Math.floor(idx / 2) * DEFAULT_H, w: DEFAULT_W, h: DEFAULT_H }
  })
}

export default function DashboardsView() {
  const [dashboards, setDashboards] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [active, setActive] = useState(null)
  const [editMode, setEditMode] = useState(false)
  const [showComments, setShowComments] = useState(false)
  const [commentText, setCommentText] = useState('')
  const [commentAuthor, setCommentAuthor] = useState('')

  const loadList = () => api.listDashboards().then((d) => setDashboards(d.dashboards || []))
  useEffect(() => { loadList() }, [])
  useEffect(() => { if (activeId) api.getDashboard(activeId).then(setActive) }, [activeId])
  useEffect(() => { setEditMode(false); setShowComments(false) }, [activeId])

  const layout = useMemo(() => buildLayout(active?.charts || [], active?.layout), [active])

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
  const rename = async (d, e) => {
    e.stopPropagation()
    const name = prompt('Rename dashboard:', d.name)
    if (!name || name === d.name) return
    try {
      await api.renameDashboard(d.id, name)
      loadList()
      if (d.id === activeId) setActive(await api.getDashboard(activeId))
    } catch (err) { alert(err.message) }
  }
  const unpin = async (chartId) => {
    await api.unpinChart(activeId, chartId)
    setActive(await api.getDashboard(activeId))
  }
  const changeType = async (chartId, type) => {
    await api.updateChartType(activeId, chartId, type)
  }
  const saveLayout = async (newLayout) => {
    try { await api.updateDashboardLayout(activeId, newLayout) } catch (err) { alert(err.message) }
  }
  const addComment = async () => {
    const text = commentText.trim()
    if (!text) return
    setCommentText('')
    try {
      await api.addDashboardComment(activeId, text, commentAuthor)
      setActive(await api.getDashboard(activeId))
    } catch (err) { alert(err.message) }
  }
  const removeComment = async (commentId) => {
    try {
      await api.deleteDashboardComment(activeId, commentId)
      setActive(await api.getDashboard(activeId))
    } catch (err) { alert(err.message) }
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
                ${d.id === activeId ? 'bg-accent/10 text-accent' : 'text-ink-dim hover:bg-panel hover:text-ink'}`}
            >
              <span className="truncate">{d.name} <span className="text-ink-faint">({d.chart_count})</span></span>
              <span className="flex items-center gap-1 opacity-60 group-hover:opacity-100 shrink-0">
                <button onClick={(e) => rename(d, e)} className="text-ink-faint hover:text-ink transition"><Pencil size={12} /></button>
                <button onClick={(e) => remove(d.id, e)} className="text-ink-faint hover:text-bad transition">&times;</button>
              </span>
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
            <div className="flex items-center justify-between mb-4 gap-3">
              <h2 className="text-lg font-semibold text-ink flex items-center gap-2"><LayoutDashboard size={18} className="text-ink-faint" />{active.name}</h2>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setShowComments((v) => !v)}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition flex items-center gap-1.5
                    ${showComments ? 'bg-accent/10 border-accent/30 text-accent' : 'bg-panel border-edge text-ink-dim hover:text-ink hover:border-edge-bright'}`}
                >
                  <MessageSquare size={13} /> Comments{active.comments?.length ? ` (${active.comments.length})` : ''}
                </button>
                {active.charts?.length > 0 && (
                  <button
                    onClick={() => setEditMode((v) => !v)}
                    className={`text-xs px-3 py-1.5 rounded-lg border transition flex items-center gap-1.5
                      ${editMode ? 'bg-accent text-white border-accent' : 'bg-panel border-edge text-ink-dim hover:text-ink hover:border-edge-bright'}`}
                  >
                    {editMode ? <Check size={13} /> : <LayoutGrid size={13} />} {editMode ? 'Done' : 'Edit Layout'}
                  </button>
                )}
              </div>
            </div>

            <div className="flex gap-5 items-start">
              <div className="flex-1 min-w-0">
                {active.charts?.length ? (
                  <ResponsiveGridLayout
                    className="layout"
                    layout={layout}
                    cols={COLS}
                    rowHeight={ROW_HEIGHT}
                    isDraggable={editMode}
                    isResizable={editMode}
                    draggableHandle=".chart-drag-handle"
                    onDragStop={(l) => saveLayout(l)}
                    onResizeStop={(l) => saveLayout(l)}
                    margin={[16, 16]}
                    compactType="vertical"
                  >
                    {active.charts.map((c) => (
                      <div key={c.id}>
                        <ChartCard
                          chart={c}
                          fill
                          dragHandle={editMode}
                          onTypeChange={(t) => changeType(c.id, t)}
                          onUnpin={editMode ? () => unpin(c.id) : undefined}
                        />
                      </div>
                    ))}
                  </ResponsiveGridLayout>
                ) : (
                  <div className="text-sm text-ink-faint">No charts pinned yet. Pin one from a chat or agent result.</div>
                )}
              </div>

              {showComments && (
                <div className="w-80 shrink-0 card p-4 flex flex-col gap-3 max-h-[calc(100vh-220px)]">
                  <h3 className="text-sm font-semibold text-ink">Comments</h3>
                  <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0">
                    {(active.comments || []).length === 0 && (
                      <div className="text-xs text-ink-faint">No comments yet.</div>
                    )}
                    {(active.comments || []).map((c) => (
                      <div key={c.id} className="group text-xs bg-panel border border-edge rounded-lg p-2.5">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-medium text-ink">{c.author}</span>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-ink-faint">{new Date(c.created_at).toLocaleString()}</span>
                            <button onClick={() => removeComment(c.id)} className="opacity-0 group-hover:opacity-100 text-ink-faint hover:text-bad transition"><Trash2 size={11} /></button>
                          </div>
                        </div>
                        <div className="text-ink-dim whitespace-pre-wrap">{c.text}</div>
                      </div>
                    ))}
                  </div>
                  <div className="flex flex-col gap-1.5 pt-2 border-t border-edge">
                    <input
                      className="text-xs bg-panel border border-edge rounded-lg px-2.5 py-1.5 text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent"
                      placeholder="Your name (optional)"
                      value={commentAuthor}
                      onChange={(e) => setCommentAuthor(e.target.value)}
                    />
                    <div className="flex gap-1.5">
                      <textarea
                        className="flex-1 text-xs bg-panel border border-edge rounded-lg px-2.5 py-1.5 text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent resize-none"
                        rows={2}
                        placeholder="Add a comment…"
                        value={commentText}
                        onChange={(e) => setCommentText(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); addComment() } }}
                      />
                      <button onClick={addComment} className="px-2.5 rounded-lg grad text-white shrink-0 hover:opacity-90 transition"><Send size={13} /></button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
