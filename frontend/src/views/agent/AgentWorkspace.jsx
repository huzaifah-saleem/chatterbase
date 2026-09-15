// Per-agent workspace: Chat | Tasks | Skills | Knowledge | Settings.
// "general" is a pseudo-persona (id in the URL, nothing in the store) -
// only Tasks applies to it, matching the old app's General/persona split.
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import ChatTab from './ChatTab'
import TasksTab from './TasksTab'
import SkillsTab from './SkillsTab'
import KnowledgeTab from './KnowledgeTab'
import SettingsTab from './SettingsTab'

const TABS_GENERAL = [{ key: 'tasks', label: 'Tasks', icon: '✅' }]
const TABS_PERSONA = [
  { key: 'chat', label: 'Chat', icon: '💬' },
  { key: 'tasks', label: 'Tasks', icon: '✅' },
  { key: 'skills', label: 'Skills', icon: '🧠' },
  { key: 'knowledge', label: 'Knowledge', icon: '🗄️' },
  { key: 'settings', label: 'Settings', icon: '⚙️' },
]

export default function AgentWorkspace() {
  const { id } = useParams()
  const isGeneral = id === 'general'
  const navigate = useNavigate()
  const [persona, setPersona] = useState(null)
  const [tab, setTab] = useState(isGeneral ? 'tasks' : 'chat')

  useEffect(() => {
    setTab(isGeneral ? 'tasks' : 'chat')
    if (isGeneral) { setPersona(null); return }
    api.listPersonas().then((d) => {
      const p = (d.personas || []).find((x) => x.id === id)
      if (!p) { navigate('/agents'); return }
      setPersona(p)
    })
  }, [id])

  const tabs = isGeneral ? TABS_GENERAL : TABS_PERSONA
  const color = persona?.color || '#8b94a7'

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="border-b border-edge px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/agents')} className="text-ink-faint hover:text-ink text-sm">&larr;</button>
          <div className="w-9 h-9 rounded-lg flex items-center justify-center text-lg" style={{ background: `${color}22`, border: `1px solid ${color}55` }}>
            {isGeneral ? '⚡' : (persona?.emoji || '🤖')}
          </div>
          <div>
            <h2 className="text-sm font-semibold text-ink">{isGeneral ? 'General' : (persona?.name || '…')}</h2>
            {!isGeneral && persona?.tagline && <p className="text-xs text-ink-dim">{persona.tagline}</p>}
          </div>
        </div>
        <div className="flex gap-1 bg-panel border border-edge rounded-xl p-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5
                ${tab === t.key ? 'bg-accent text-white' : 'text-ink-dim hover:text-ink'}`}
            >
              <span>{t.icon}</span>{t.label}
            </button>
          ))}
        </div>
      </div>

      {!isGeneral && !persona ? (
        <div className="flex-1 flex items-center justify-center text-ink-faint text-sm">Loading…</div>
      ) : (
        <>
          {tab === 'chat' && <ChatTab personaId={id} />}
          {tab === 'tasks' && <TasksTab personaId={isGeneral ? null : id} />}
          {tab === 'skills' && <SkillsTab personaId={id} />}
          {tab === 'knowledge' && <KnowledgeTab persona={persona} onUpdated={setPersona} />}
          {tab === 'settings' && <SettingsTab persona={persona} onUpdated={setPersona} />}
        </>
      )}
    </div>
  )
}
