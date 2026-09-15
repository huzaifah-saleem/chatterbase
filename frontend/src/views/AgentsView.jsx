// Agent marketplace: card grid, the visual centerpiece of the redesign.
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import AgentCard from '../components/AgentCard'
import AgentFormModal from '../components/AgentFormModal'
import { useNavigate } from 'react-router-dom'

export default function AgentsView() {
  const [personas, setPersonas] = useState([])
  const [skillCounts, setSkillCounts] = useState({})
  const [showCreate, setShowCreate] = useState(false)
  const navigate = useNavigate()

  const load = async () => {
    const d = await api.listPersonas()
    setPersonas(d.personas || [])
    const counts = {}
    await Promise.all((d.personas || []).map(async (p) => {
      try { counts[p.id] = (await api.listSkills(p.id)).skills?.length || 0 } catch { counts[p.id] = 0 }
    }))
    setSkillCounts(counts)
  }
  useEffect(() => { load() }, [])

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-ink">Agent Marketplace</h1>
          <p className="text-sm text-ink-dim mt-1">Named, saved experts - each with its own domain knowledge, skills, and database binding.</p>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <AgentCard persona={{ name: 'General', emoji: '⚡' }} isGeneral />
          {personas.map((p) => (
            <AgentCard key={p.id} persona={p} skillCount={skillCounts[p.id]} />
          ))}
          <button
            onClick={() => setShowCreate(true)}
            className="card card-hover border-dashed flex flex-col items-center justify-center gap-2 p-5 text-ink-faint hover:text-ink min-h-[168px]"
          >
            <span className="text-3xl grad-text font-light">+</span>
            <span className="text-sm font-medium">Create Agent</span>
          </button>
        </div>
      </div>

      {showCreate && (
        <AgentFormModal
          onClose={() => setShowCreate(false)}
          onSaved={(p) => { setShowCreate(false); load(); navigate(`/agents/${p.id}`) }}
        />
      )}
    </div>
  )
}
