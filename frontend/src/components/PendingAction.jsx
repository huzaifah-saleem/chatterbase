// Renders one dispatch step / pending action, by tool: "task" (a subagent
// dispatch - subagent_type + description) or "run_python" (a syntax-lit
// code block). Shared between Tasks (RunCard.jsx) and Chat (ChatTab.jsx),
// since run_python is gated identically in both modes (see
// agent_orchestrator.py's W2 notes) and both need the same rendering for
// completed steps and pending approvals.
import { Blocks } from './Blocks'

const badgeCls = (subagent) => (subagent || '').includes('dashboard')
  ? 'bg-good/15 text-good'
  : 'bg-accent/15 text-accent'

export function PendingAction({ tool, args, decision, blocks }) {
  const isCode = tool === 'run_python'
  return (
    <div className={`border-l-2 pl-3 py-1 ${isCode ? 'border-warn' : 'border-edge'}`}>
      <div className="flex items-center gap-2 text-xs flex-wrap">
        <span className={`px-2 py-0.5 rounded-full font-semibold uppercase tracking-wide text-[10px] ${isCode ? 'bg-warn/15 text-warn' : badgeCls(args?.subagent_type)}`}>
          {isCode ? 'run python' : args?.subagent_type}
        </span>
        {!isCode && <span className="text-ink-dim">{args?.description}</span>}
        {decision === 'reject' && <span className="text-ink-faint uppercase text-[10px]">rejected</span>}
      </div>
      {isCode && (
        <pre className="mt-1.5 text-xs bg-[#f1f1f4] border border-edge rounded-lg p-3 overflow-x-auto font-mono text-ink-dim">{args?.code}</pre>
      )}
      {blocks?.length > 0 && <div className="mt-2 ml-1"><Blocks blocks={blocks} /></div>}
    </div>
  )
}
