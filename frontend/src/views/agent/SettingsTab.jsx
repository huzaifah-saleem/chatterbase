import { useState } from 'react'
import { api } from '../../lib/api'
import { useNavigate } from 'react-router-dom'
import AgentFormModal from '../../components/AgentFormModal'
import { btnPrimary, btnDanger } from '../../components/Modal'

export default function SettingsTab({ persona, onUpdated }) {
  const [editing, setEditing] = useState(false)
  const navigate = useNavigate()

  const remove = async () => {
    if (!confirm(`Delete agent "${persona.name}"? Its skills and database binding go with it; past runs stay on disk but won't be reachable from here anymore.`)) return
    await api.deletePersona(persona.id)
    navigate('/agents')
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-lg mx-auto flex flex-col gap-6">
        <div className="card p-4 flex flex-col gap-3">
          <h3 className="text-sm font-semibold text-ink">Identity &amp; expertise</h3>
          <div className="text-xs text-ink-dim whitespace-pre-wrap">{persona.expertise_prompt}</div>
          <button className={btnPrimary + ' self-start'} onClick={() => setEditing(true)}>Edit</button>
        </div>

        <div className="card p-4 flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-ink">Share</h3>
          <p className="text-xs text-ink-dim">Export this agent's identity and skills as a file another Chatterbase instance can import. Chat/task history and the auto-generated database-knowledge skill are not included.</p>
          <a
            href={`/api/agent/personas/${persona.id}/export`}
            className="text-xs px-3 py-1.5 rounded-lg bg-edge hover:bg-edge-bright text-ink transition self-start"
          >
            ⬇ Export Agent
          </a>
        </div>

        <div className="card p-4 flex flex-col gap-2 border-bad/30">
          <h3 className="text-sm font-semibold text-bad">Danger zone</h3>
          <p className="text-xs text-ink-dim">Permanently delete this agent, its skills, and its database binding.</p>
          <button className={btnDanger + ' self-start !text-sm !px-3 !py-1.5 border border-bad/30'} onClick={remove}>Delete Agent</button>
        </div>
      </div>

      {editing && (
        <AgentFormModal
          persona={persona}
          onClose={() => setEditing(false)}
          onSaved={(p) => { setEditing(false); onUpdated(p) }}
        />
      )}
    </div>
  )
}
