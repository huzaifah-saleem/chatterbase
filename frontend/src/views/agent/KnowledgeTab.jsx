// Binds this agent to a database and syncs its schema (table list + DDLs)
// into an auto-generated skill (knowledge_sync.py) - the data-agent reads
// it on demand via deepagents' own progressive disclosure, same mechanism
// as any hand-written skill (SkillsTab.jsx).
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { inputCls, btnPrimary } from '../../components/Modal'

export default function KnowledgeTab({ persona, onUpdated }) {
  const [databases, setDatabases] = useState([])
  const [selected, setSelected] = useState(persona.database || '')
  const [skill, setSkill] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    api.listDatabases().then((d) => setDatabases(d.databases || [])).catch((e) => setLoadError(e.message))
    api.getKnowledge(persona.id).then((s) => setSkill(s?.body ? s : null)).catch(() => {})
  }, [persona.id])

  const doSync = async () => {
    if (!selected) { alert('Choose a database first.'); return }
    setSyncing(true)
    try {
      const result = await api.syncKnowledge(persona.id, selected)
      setSkill(result)
      onUpdated(result.persona)
    } catch (e) {
      alert('Sync failed: ' + e.message)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto flex flex-col gap-4">
        <div>
          <h3 className="text-sm font-semibold text-ink">Database Knowledge</h3>
          <p className="text-xs text-ink-dim mt-0.5">Bind this agent to a database and sync its schema - table names and DDLs become a skill it consults before writing SQL, instead of discovering the schema fresh every time.</p>
        </div>

        <div className="card p-4 flex flex-col gap-3">
          <div className="flex gap-2">
            <select className={inputCls} value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">Select a database...</option>
              {databases.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <button className={btnPrimary} onClick={doSync} disabled={syncing}>{syncing ? 'Syncing...' : 'Sync'}</button>
          </div>
          {loadError && <div className="text-xs text-bad">Couldn't load database list: {loadError}</div>}
          {persona.database && (
            <div className="text-xs text-ink-faint">
              Bound to <strong className="text-ink-dim">{persona.database}</strong>
              {persona.last_synced && ` · last synced ${new Date(persona.last_synced).toLocaleString()}`}
            </div>
          )}
        </div>

        {skill && (
          <div className="card p-4">
            <div className="text-xs text-ink-dim mb-2">{skill.description}</div>
            <pre className="text-xs bg-[#0d1118] border border-edge rounded-lg p-3 overflow-auto max-h-96 font-mono text-ink-dim whitespace-pre-wrap">{skill.body}</pre>
          </div>
        )}
      </div>
    </div>
  )
}
