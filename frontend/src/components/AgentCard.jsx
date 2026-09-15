// Marketplace-style agent card - the visual centerpiece of the redesign.
import { useNavigate } from 'react-router-dom'

export default function AgentCard({ persona, skillCount, isGeneral }) {
  const navigate = useNavigate()
  const color = persona.color || '#f27340'
  return (
    <button
      onClick={() => navigate(`/agents/${isGeneral ? 'general' : persona.id}`)}
      className="card card-hover text-left p-5 flex flex-col gap-3 rise"
    >
      <div className="flex items-center justify-between">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl shrink-0"
          style={{ background: `${color}22`, border: `1px solid ${color}55` }}
        >
          {persona.emoji || (isGeneral ? '⚡' : '🤖')}
        </div>
        {persona.database && (
          <span className="text-[10px] px-2 py-1 rounded-full bg-panel border border-edge text-ink-dim">🗄 {persona.database}</span>
        )}
      </div>
      <div>
        <h3 className="text-sm font-semibold text-ink">{persona.name}</h3>
        <p className="text-xs text-ink-dim mt-1 line-clamp-2">
          {persona.tagline || persona.expertise_prompt || 'General-purpose data assistant, no custom expertise.'}
        </p>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-ink-faint mt-auto pt-2 border-t border-edge">
        {!isGeneral && <span>🧠 {skillCount ?? 0} skill{skillCount === 1 ? '' : 's'}</span>}
        {isGeneral && <span>Default · not customizable</span>}
      </div>
    </button>
  )
}
