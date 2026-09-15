// One-shot, per-dispatch-gated task runs. Parity port of the old Agent tab
// flow: submit a request, approve/reject each sub-agent dispatch as the
// orchestrator proposes it live, browse + replay past runs.
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import RunCard from '../../components/RunCard'
import { Blocks } from '../../components/Blocks'

export default function TasksTab({ personaId }) {
  const [history, setHistory] = useState([])
  const [liveRuns, setLiveRuns] = useState([]) // [{id, request, steps, pending_actions, status}]
  const [busyRunId, setBusyRunId] = useState(null) // 'starting' handled separately
  const [input, setInput] = useState('')
  const [starting, setStarting] = useState(false)
  const [replay, setReplay] = useState(null)

  const loadHistory = () => api.listRuns(personaId).then((d) => setHistory(d.runs || []))
  useEffect(() => { loadHistory(); setLiveRuns([]); setReplay(null) }, [personaId])

  const submit = async () => {
    const text = input.trim()
    if (!text || starting) return
    setInput('')
    setStarting(true)
    try {
      const run = await api.startRun(text, personaId)
      setLiveRuns((prev) => [...prev, { id: run.id, request: run.request, steps: [], pending_actions: run.pending_actions, status: run.status }])
      loadHistory()
    } catch (e) { alert(e.message) } finally { setStarting(false) }
  }

  const resume = async (runId, decision) => {
    setBusyRunId(runId)
    try {
      const run = await api.resumeRun(runId, decision)
      setLiveRuns((prev) => prev.map((s) => {
        if (s.id !== runId) return s
        const newSteps = [...s.steps]
        for (const a of s.pending_actions || []) newSteps.push({ tool: a.tool, args: a.args, decision })
        if (newSteps.length && run.blocks?.length) newSteps[newSteps.length - 1].blocks = run.blocks
        return { ...s, steps: newSteps, pending_actions: run.pending_actions, status: run.status }
      }))
      if (run.status !== 'interrupted') loadHistory()
    } catch (e) { alert(e.message) } finally { setBusyRunId(null) }
  }

  const openReplay = async (runId) => {
    setReplay({ id: runId, loading: true })
    try {
      const run = await api.getRun(runId)
      setReplay({ id: runId, request: run.title || run.request, status: run.status, blocks: run.blocks })
    } catch (e) { setReplay(null); alert(e.message) }
  }

  const removeRun = async (runId, e) => {
    e.stopPropagation()
    if (!confirm('Delete this run?')) return
    try {
      await api.deleteRun(runId)
      if (replay?.id === runId) setReplay(null)
      loadHistory()
    } catch (e) { alert(e.message) }
  }

  const renameRun = async (r, e) => {
    e.stopPropagation()
    const title = prompt('Rename run:', r.request)
    if (!title || title === r.request) return
    try {
      await api.renameRun(r.id, title)
      loadHistory()
      if (replay?.id === r.id) setReplay((prev) => ({ ...prev, request: title }))
    } catch (err) { alert(err.message) }
  }

  return (
    <div className="flex-1 flex min-h-0">
      <aside className="w-72 shrink-0 border-r border-edge overflow-y-auto p-3 flex flex-col gap-1">
        <div className="text-[11px] uppercase tracking-wide text-ink-faint px-2 mb-1">History</div>
        {history.map((r) => (
          <div
            key={r.id}
            onClick={() => openReplay(r.id)}
            className={`group flex items-start justify-between gap-1 px-3 py-2 rounded-lg text-xs cursor-pointer transition
              ${r.id === replay?.id ? 'bg-accent/15 text-accent-hot' : 'text-ink-dim hover:bg-panel hover:text-ink'}`}
          >
            <div className="min-w-0">
              <div className="line-clamp-2">{r.request}</div>
              <div className="text-[10px] text-ink-faint mt-0.5">{(r.status || '').replace('_', ' ')}</div>
            </div>
            <span className="flex items-center gap-1 shrink-0 opacity-60 group-hover:opacity-100">
              <button onClick={(e) => renameRun(r, e)} className="text-ink-faint hover:text-ink transition">✏️</button>
              <button onClick={(e) => removeRun(r.id, e)} className="text-ink-faint hover:text-bad transition">&times;</button>
            </span>
          </div>
        ))}
        {history.length === 0 && <div className="px-3 py-2 text-xs text-ink-faint">No runs yet</div>}
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-3">
          {replay && (
            replay.loading ? <div className="text-xs text-ink-faint">Loading…</div> : (
              <div className="card p-4">
                <div className="text-xs italic text-ink-dim mb-2">"{replay.request}"</div>
                <Blocks blocks={replay.blocks} />
                <div className={`text-[10px] font-semibold uppercase tracking-wide mt-2 ${replay.status === 'done' ? 'text-good' : 'text-ink-faint'}`}>{(replay.status || '').replace('_', ' ')}</div>
              </div>
            )
          )}
          {liveRuns.map((s) => (
            <RunCard
              key={s.id}
              state={s}
              busy={busyRunId === s.id ? 'running' : null}
              onResume={(decision) => resume(s.id, decision)}
            />
          ))}
          {liveRuns.length === 0 && !replay && (
            <div className="flex-1 flex items-center justify-center text-ink-faint text-sm">
              Describe a task below - a plan gets proposed step by step; nothing runs until you approve it.
            </div>
          )}
        </div>

        <div className="border-t border-edge p-4">
          <div className="flex gap-2">
            <textarea
              className="flex-1 resize-none rounded-xl bg-panel border border-edge px-4 py-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition"
              rows={1}
              placeholder="What do you want done? e.g. 'Check my database sizes and chart them'"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
            />
            <button onClick={submit} disabled={starting} className="px-5 rounded-xl grad text-white text-sm font-semibold hover:opacity-90 transition disabled:opacity-40">
              {starting ? 'Starting…' : 'Plan'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
