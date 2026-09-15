// App shell: header with live status pills, content area, and a vertical
// icon rail docked on the RIGHT (per the redesign brief - nav lives beside
// the content it controls, not above it).
import { NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import SettingsModal from './SettingsModal'

const NAV = [
  { to: '/', label: 'Chats', icon: '💬', end: true },
  { to: '/dashboards', label: 'Dashboards', icon: '📊' },
  { to: '/agents', label: 'Agents', icon: '🤖' },
  { to: '/activity', label: 'Activity', icon: '📡' },
]

function Logo() {
  return (
    <div className="w-8 h-8 rounded-lg grad flex items-center justify-center text-white font-bold text-sm shrink-0">C</div>
  )
}

function StatusPill({ ok, label, detail }) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-ink-dim">
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-good' : 'bg-bad'} ${ok === null ? 'pulse bg-warn' : ''}`} />
      <span>{label}{detail ? `: ${detail}` : ''}</span>
    </div>
  )
}

export default function Shell() {
  const [mcp, setMcp] = useState({ ok: null, detail: '' })
  const [llm, setLlm] = useState({ ok: null, detail: '' })
  const [settingsOpen, setSettingsOpen] = useState(false)

  useEffect(() => {
    let alive = true
    async function poll() {
      try {
        const h = await api.mcpHealth()
        if (!alive) return
        const okServers = (h.servers || []).filter((s) => s.status === 'ok').length
        setMcp({ ok: okServers > 0, detail: `${okServers} server${okServers === 1 ? '' : 's'}, ${h.total_tools ?? 0} tools` })
      } catch { if (alive) setMcp({ ok: false, detail: 'unreachable' }) }
      try {
        const l = await api.llmHealth()
        if (!alive) return
        setLlm({ ok: true, detail: l.provider || '' })
      } catch { if (alive) setLlm({ ok: false, detail: 'unreachable' }) }
    }
    poll()
    const id = setInterval(poll, 20000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  return (
    <div className="h-full flex flex-col bg-base">
      <header className="h-14 shrink-0 border-b border-edge flex items-center justify-between px-5">
        <div className="flex items-center gap-3">
          <Logo />
          <span className="font-semibold text-ink">Chatterbase</span>
        </div>
        <div className="flex items-center gap-5">
          <StatusPill ok={mcp.ok} label="MCP" detail={mcp.detail} />
          <StatusPill ok={llm.ok} label="LLM" detail={llm.detail} />
          <button
            onClick={() => setSettingsOpen(true)}
            className="text-xs px-3 py-1.5 rounded-lg bg-panel border border-edge text-ink-dim hover:text-ink hover:border-edge-bright transition"
          >
            ⚙ Settings
          </button>
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        <main className="flex-1 min-w-0 flex flex-col">
          <Outlet />
        </main>

        <nav className="w-20 shrink-0 border-l border-edge flex flex-col items-center gap-2 py-4">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `w-14 h-14 rounded-xl flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition
                 ${isActive ? 'grad text-white shadow-lg shadow-accent/20' : 'text-ink-dim hover:bg-panel hover:text-ink'}`
              }
            >
              <span className="text-lg leading-none">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </div>

      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  )
}
