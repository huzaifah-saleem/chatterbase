// One gated task run: request text, completed dispatch/code-approval steps,
// and either a pending-approval prompt or a final status. Parity port of
// the old plan-card, restyled.
import { useEffect, useRef, useState } from 'react'
import { PendingAction } from './PendingAction'

function useElapsed(active) {
  const [secs, setSecs] = useState(0)
  const startRef = useRef(null)
  useEffect(() => {
    if (!active) { setSecs(0); return }
    startRef.current = Date.now()
    const id = setInterval(() => setSecs(Math.floor((Date.now() - startRef.current) / 1000)), 1000)
    return () => clearInterval(id)
  }, [active])
  return secs
}

export default function RunCard({ state, onResume, busy }) {
  const secs = useElapsed(!!busy)

  return (
    <div className="card p-4 rise flex flex-col gap-3">
      <div className="text-xs italic text-ink-dim">"{state.request}"</div>
      {state.steps?.length > 0 && (
        <div className="flex flex-col gap-2">
          {state.steps.map((s, i) => <PendingAction key={i} {...s} />)}
        </div>
      )}

      {busy ? (
        <div className="text-xs text-ink-faint flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-accent pulse" /> {busy === 'starting' ? 'Starting' : 'Running'}... ({secs}s)
        </div>
      ) : state.status === 'interrupted' ? (
        <>
          <div className="flex flex-col gap-2">
            {(state.pending_actions || []).map((a, i) => <PendingAction key={i} tool={a.tool} args={a.args} />)}
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => onResume('reject')} className="text-xs px-3 py-1.5 rounded-lg bg-panel border border-edge text-ink-dim hover:text-bad hover:border-bad/50 transition">Reject</button>
            <button onClick={() => onResume('approve')} className="text-xs px-3 py-1.5 rounded-lg grad text-white font-medium hover:opacity-90 transition">Approve &amp; Run</button>
          </div>
        </>
      ) : (
        <div className={`text-[10px] font-semibold uppercase tracking-wide ${state.status === 'done' ? 'text-good' : 'text-ink-faint'}`}>{(state.status || '').replace('_', ' ')}</div>
      )}
    </div>
  )
}
