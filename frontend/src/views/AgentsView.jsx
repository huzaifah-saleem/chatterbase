// Agent marketplace: card grid, the visual centerpiece of the redesign.
import { useEffect, useRef, useState } from 'react'
import { Upload, Plus } from 'lucide-react'
import { api } from '../lib/api'
import AgentCard from '../components/AgentCard'
import AgentFormModal from '../components/AgentFormModal'
import { useNavigate } from 'react-router-dom'

export default function AgentsView() {
  const [personas, setPersonas] = useState([])
  const [skillCounts, setSkillCounts] = useState({})
  const [showCreate, setShowCreate] = useState(false)
  const [importing, setImporting] = useState(false)
  const fileInputRef = useRef(null)
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

  const importFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-selecting the same file next time
    if (!file) return
    setImporting(true)
    try {
      const text = await file.text()
      const payload = JSON.parse(text)
      const p = await api.importPersona(payload)
      await load()
      navigate(`/agents/${p.id}`)
    } catch (err) {
      alert(`Import failed: ${err.message}`)
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-ink">Agent Marketplace</h1>
            <p className="text-sm text-ink-dim mt-1">Named, saved experts - each with its own domain knowledge, skills, and database binding.</p>
          </div>
          <div>
            <input ref={fileInputRef} type="file" accept="application/json,.json" className="hidden" onChange={importFile} />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={importing}
              className="text-xs px-3 py-1.5 rounded-lg bg-panel border border-edge text-ink-dim hover:text-ink hover:border-edge-bright transition disabled:opacity-50 shrink-0 flex items-center gap-1.5"
            >
              <Upload size={13} /> {importing ? 'Importing…' : 'Import Agent'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <AgentCard persona={{ name: 'General' }} isGeneral />
          {personas.map((p) => (
            <AgentCard key={p.id} persona={p} skillCount={skillCounts[p.id]} />
          ))}
          <button
            onClick={() => setShowCreate(true)}
            className="card card-hover border-dashed flex flex-col items-center justify-center gap-2 p-5 text-ink-faint hover:text-ink min-h-[168px]"
          >
            <Plus size={22} className="text-accent" strokeWidth={2} />
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
