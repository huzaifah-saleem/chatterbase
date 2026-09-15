// Create or edit an agent persona - name, expertise prompt, and the
// marketplace card cosmetics (an accent color; the avatar itself is
// always the name's initial, not a picked icon - simpler and reads more
// like an enterprise app's default avatar than a per-agent icon picker).
import { useState } from 'react'
import { api } from '../lib/api'
import Modal, { Field, inputCls, btnPrimary, btnSecondary } from './Modal'

const COLOR_CHOICES = ['#e8590c', '#2f6fed', '#1e8e3e', '#7c4dff', '#d92d20', '#0891b2', '#b45309']

export default function AgentFormModal({ persona, onClose, onSaved }) {
  const isEdit = !!persona
  const [name, setName] = useState(persona?.name || '')
  const [tagline, setTagline] = useState(persona?.tagline || '')
  const [expertise, setExpertise] = useState(persona?.expertise_prompt || '')
  const [color, setColor] = useState(persona?.color || COLOR_CHOICES[0])
  const [busy, setBusy] = useState(false)
  const initial = (name || '?').trim().charAt(0).toUpperCase()

  const save = async () => {
    if (!name.trim() || !expertise.trim()) { alert('Name and expertise are required.'); return }
    setBusy(true)
    try {
      const payload = { name: name.trim(), expertise_prompt: expertise.trim(), tagline: tagline.trim(), color }
      const saved = isEdit ? await api.updatePersona(persona.id, payload) : await api.createPersona(payload)
      onSaved(saved)
    } catch (e) { alert(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal title={isEdit ? 'Edit Agent' : 'New Agent'} onClose={onClose}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="w-14 h-14 rounded-xl flex items-center justify-center text-lg font-semibold shrink-0" style={{ background: `${color}18`, border: `1px solid ${color}40`, color }}>
            {initial}
          </div>
          <div className="flex-1 flex flex-col gap-2">
            <div className="flex gap-1.5">
              {COLOR_CHOICES.map((c) => (
                <button key={c} onClick={() => setColor(c)} className={`w-6 h-6 rounded-full ${color === c ? 'ring-2 ring-offset-2 ring-offset-card ring-accent' : ''}`} style={{ background: c }} />
              ))}
            </div>
          </div>
        </div>

        <Field label="Name"><input className={inputCls} placeholder="e.g. Telecom Analyst" value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Tagline (optional, shown on the card)"><input className={inputCls} placeholder="e.g. Churn & network KPI specialist" value={tagline} onChange={(e) => setTagline(e.target.value)} /></Field>
        <Field label="What should this agent be an expert in?">
          <textarea
            className={inputCls + ' min-h-28 resize-y'}
            placeholder="e.g. You specialize in telecom call-detail records, network KPIs, and churn analysis. Favor per-region and per-plan breakdowns."
            value={expertise}
            onChange={(e) => setExpertise(e.target.value)}
          />
        </Field>

        <div className="flex justify-end gap-2 mt-1">
          <button className={btnSecondary} onClick={onClose}>Cancel</button>
          <button className={btnPrimary} onClick={save} disabled={busy}>{isEdit ? 'Save' : 'Create'}</button>
        </div>
      </div>
    </Modal>
  )
}
