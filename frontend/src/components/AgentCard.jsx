// Marketplace-style agent card - the visual centerpiece of the redesign.
import { useNavigate } from 'react-router-dom'
import { Zap, Database, Sparkles } from 'lucide-react'

export default function AgentCard({ persona, skillCount, isGeneral }) {
  const navigate = useNavigate()
  const color = persona.color || '#e8590c'
  const initial = (persona.name || '?').trim().charAt(0).toUpperCase()
  return (
    <button
      onClick={() => navigate(`/agents/${isGeneral ? 'general' : persona.id}`)}
      className="card card-hover text-left p-5 flex flex-col gap-3 rise"
    >
      <div className="flex items-center justify-between">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: `${color}18`, border: `1px solid ${color}40`, color }}
        >
          {isGeneral ? <Zap size={20} strokeWidth={1.75} /> : <span className="text-lg font-semibold">{initial}</span>}
        </div>
        {persona.database && (
          <span className="text-[10px] px-2 py-1 rounded-full bg-panel border border-edge text-ink-dim flex items-center gap-1"><Database size={11} />{persona.database}</span>
        )}
      </div>
      <div>
        <h3 className="text-sm font-semibold text-ink">{persona.name}</h3>
        <p className="text-xs text-ink-dim mt-1 line-clamp-2">
          {persona.tagline || persona.expertise_prompt || 'General-purpose data assistant, no custom expertise.'}
        </p>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-ink-faint mt-auto pt-2 border-t border-edge">
        {!isGeneral && <span className="flex items-center gap-1"><Sparkles size={12} />{skillCount ?? 0} skill{skillCount === 1 ? '' : 's'}</span>}
        {isGeneral && <span>Default · not customizable</span>}
      </div>
    </button>
  )
}
