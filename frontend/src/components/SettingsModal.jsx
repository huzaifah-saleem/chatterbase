// Settings: MCP servers (add/enable/delete/import) + LLM profiles
// (add/activate/delete) - parity port of the old settings modal.
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import Modal, { Field, inputCls, btnPrimary, btnSecondary, btnDanger } from './Modal'

const PROVIDER_TYPES = ['local_llm', 'lm_studio', 'nvidia_nim', 'gemini', 'openai']

export default function SettingsModal({ onClose }) {
  const [tab, setTab] = useState('mcp')
  return (
    <Modal title="Settings" onClose={onClose} wide>
      <div className="flex gap-2 mb-5 border-b border-edge">
        {['mcp', 'llm'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition ${tab === t ? 'border-accent text-ink' : 'border-transparent text-ink-dim hover:text-ink'}`}
          >
            {t === 'mcp' ? 'MCP Servers' : 'LLM Profiles'}
          </button>
        ))}
      </div>
      {tab === 'mcp' ? <McpTab /> : <LlmTab />}
    </Modal>
  )
}

function McpTab() {
  const [servers, setServers] = useState([])
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [importText, setImportText] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = () => api.listMcpServers().then((d) => setServers(d.servers || []))
  useEffect(() => { load() }, [])

  const add = async () => {
    if (!name.trim() || !url.trim()) return
    setBusy(true)
    try { await api.addMcpServer(name.trim(), url.trim()); setName(''); setUrl(''); await load() }
    catch (e) { alert(e.message) } finally { setBusy(false) }
  }
  const toggle = async (s) => { await api.updateMcpServer(s.id, { enabled: !s.enabled }); load() }
  const remove = async (id) => { if (confirm('Delete this MCP server?')) { await api.deleteMcpServer(id); load() } }
  const doImport = async () => {
    try {
      const r = await api.importMcpServers(importText)
      alert(`Added ${r.added?.length || 0}, skipped ${r.skipped?.length || 0}`)
      setImportText(''); setShowImport(false); load()
    } catch (e) { alert(e.message) }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        {servers.map((s) => (
          <div key={s.id} className="flex items-center justify-between gap-3 px-3 py-2 rounded-lg bg-panel border border-edge">
            <div className="min-w-0">
              <div className="text-sm text-ink font-medium">{s.name}</div>
              <div className="text-xs text-ink-faint truncate">{s.url}</div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={() => toggle(s)} className={`w-8 h-4.5 rounded-full transition relative ${s.enabled ? 'bg-accent' : 'bg-edge-bright'}`}>
                <span className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white transition ${s.enabled ? 'left-4' : 'left-0.5'}`} />
              </button>
              <button onClick={() => remove(s.id)} className={btnDanger}>Delete</button>
            </div>
          </div>
        ))}
        {servers.length === 0 && <div className="text-xs text-ink-faint">No MCP servers configured.</div>}
      </div>

      <div className="flex gap-2">
        <input className={inputCls} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <input className={inputCls} placeholder="http://host:port/mcp/" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className={btnPrimary} onClick={add} disabled={busy}>Add</button>
      </div>

      <button className="text-xs text-ink-dim hover:text-ink text-left" onClick={() => setShowImport((v) => !v)}>
        {showImport ? '▾' : '▸'} Import from Claude Desktop-style JSON
      </button>
      {showImport && (
        <div className="flex flex-col gap-2">
          <textarea className={inputCls + ' min-h-24 font-mono text-xs'} value={importText} onChange={(e) => setImportText(e.target.value)} placeholder='{"mcpServers": {"name": {"url": "http://host:port/mcp"}}}' />
          <button className={btnSecondary} onClick={doImport}>Import</button>
        </div>
      )}
    </div>
  )
}

function LlmTab() {
  const [profiles, setProfiles] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [form, setForm] = useState({ name: '', provider_type: 'lm_studio', url: '', model: '', api_key: '' })
  const [busy, setBusy] = useState(false)

  const load = () => api.listLlmProfiles().then((d) => { setProfiles(d.profiles || []); setActiveId(d.active_id) })
  useEffect(() => { load() }, [])

  const needsUrl = ['local_llm', 'lm_studio', 'nvidia_nim'].includes(form.provider_type)
  const needsKey = ['gemini', 'openai'].includes(form.provider_type)

  const add = async () => {
    if (!form.name.trim()) return
    setBusy(true)
    try { await api.addLlmProfile(form); setForm({ name: '', provider_type: 'lm_studio', url: '', model: '', api_key: '' }); await load() }
    catch (e) { alert(e.message) } finally { setBusy(false) }
  }
  const activate = async (id) => { await api.activateLlmProfile(id); load() }
  const remove = async (id) => { if (confirm('Delete this profile?')) { await api.deleteLlmProfile(id); load() } }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        {profiles.map((p) => (
          <div key={p.id} className="flex items-center justify-between gap-3 px-3 py-2 rounded-lg bg-panel border border-edge">
            <div className="min-w-0">
              <div className="text-sm text-ink font-medium flex items-center gap-2">
                {p.name}
                {p.id === activeId && <span className="text-[10px] px-1.5 py-0.5 rounded grad text-white">active</span>}
              </div>
              <div className="text-xs text-ink-faint truncate">{p.provider_type} · {p.model || p.url}</div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {p.id !== activeId && <button onClick={() => activate(p.id)} className={btnSecondary + ' !px-2 !py-1 text-xs'}>Activate</button>}
              <button onClick={() => remove(p.id)} className={btnDanger}>Delete</button>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-panel border border-edge">
        <Field label="Name"><input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Provider">
          <select className={inputCls} value={form.provider_type} onChange={(e) => setForm({ ...form, provider_type: e.target.value })}>
            {PROVIDER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
        {needsUrl && <Field label="URL"><input className={inputCls} value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} /></Field>}
        {needsKey && <Field label="API Key"><input className={inputCls} type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} /></Field>}
        <Field label="Model"><input className={inputCls} value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} /></Field>
        <div className="col-span-2"><button className={btnPrimary} onClick={add} disabled={busy}>Add Profile</button></div>
      </div>
    </div>
  )
}
