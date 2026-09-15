// Create or edit an agent persona - name, expertise prompt, and the
// marketplace card cosmetics (emoji/color/tagline).
import { useState } from 'react'
import { api } from '../lib/api'
import Modal, { Field, inputCls, btnPrimary, btnSecondary } from './Modal'

const EMOJI_CHOICES = ['🤖', '📊', '🧮', '📡', '🛰️', '🧠', '🔍', '💾', '📈', '🏦', '📞', '🛒']
const COLOR_CHOICES = ['#f27340', '#4C8BF5', '#3ecf8e', '#a970ff', '#f0546a', '#00BCD4', '#f5b940']

export default function AgentFormModal({ persona, onClose, onSaved }) {
  const isEdit = !!persona
  const [name, setName] = useState(persona?.name || '')
  const [tagline, setTagline] = useState(persona?.tagline || '')
  const [expertise, setExpertise] = useState(persona?.expertise_prompt || '')
  const [emoji, setEmoji] = useState(persona?.emoji || EMOJI_CHOICES[0])
  const [color, setColor] = useState(persona?.color || COLOR_CHOICES[0])
  const [busy, setBusy] = useState(false)

  const save = async () => {
    if (!name.trim() || !expertise.trim()) { alert('Name and expertise are required.'); return }
    setBusy(true)
    try {
      const payload = { name: name.trim(), expertise_prompt: expertise.trim(), tagline: tagline.trim(), emoji, color }
      const saved = isEdit ? await api.updatePersona(persona.id, payload) : await api.createPersona(payload)
      onSaved(saved)
    } catch (e) { alert(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal title={isEdit ? 'Edit Agent' : 'New Agent'} onClose={onClose}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="w-14 h-14 rounded-xl flex items-center justify-center text-2xl shrink-0" style={{ background: `${color}22`, border: `1px solid ${color}55` }}>
            {emoji}
          </div>
          <div className="flex-1 flex flex-col gap-2">
            <div className="flex gap-1.5 flex-wrap">
              {EMOJI_CHOICES.map((e) => (
                <button key={e} onClick={() => setEmoji(e)} className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm ${emoji === e ? 'bg-edge-bright ring-1 ring-accent' : 'hover:bg-panel'}`}>{e}</button>
              ))}
            </div>
            <div className="flex gap-1.5">
              {COLOR_CHOICES.map((c) => (
                <button key={c} onClick={() => setColor(c)} className={`w-5 h-5 rounded-full ${color === c ? 'ring-2 ring-offset-2 ring-offset-card ring-white' : ''}`} style={{ background: c }} />
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
