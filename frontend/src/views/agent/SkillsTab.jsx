// Markdown playbooks (deepagents SKILL.md format) scoped to this persona.
// Parity port of the old skills sub-editor, as its own tab.
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { inputCls, btnPrimary, btnSecondary } from '../../components/Modal'

export default function SkillsTab({ personaId }) {
  const [skills, setSkills] = useState([])
  const [editing, setEditing] = useState(null) // null | {} (new) | {slug,...} (existing)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [body, setBody] = useState('')

  const load = () => api.listSkills(personaId).then((d) => setSkills(d.skills || []))
  useEffect(() => { load() }, [personaId])

  const openNew = () => { setEditing({}); setName(''); setDescription(''); setBody('') }
  const openEdit = async (slug) => {
    const skill = await api.getSkill(personaId, slug)
    setEditing(skill)
    setName(skill.name); setDescription(skill.description); setBody(skill.body)
  }
  const cancel = () => setEditing(null)

  const save = async () => {
    if (!description.trim() || !body.trim()) { alert('Description and playbook body are required.'); return }
    try {
      if (editing?.slug) {
        await api.updateSkill(personaId, editing.slug, { description: description.trim(), body: body.trim() })
      } else {
        if (!name.trim()) { alert('A skill name is required.'); return }
        await api.createSkill(personaId, { name: name.trim(), description: description.trim(), body: body.trim() })
      }
      setEditing(null)
      load()
    } catch (e) { alert(e.message) }
  }
  const remove = async (slug, name, e) => {
    e.stopPropagation()
    if (!confirm(`Delete skill "${name}"?`)) return
    await api.deleteSkill(personaId, slug)
    load()
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-ink">Skills</h3>
            <p className="text-xs text-ink-dim mt-0.5">Markdown playbooks this agent reads on demand (deepagents progressive disclosure) - give it concrete steps instead of hoping it improvises.</p>
          </div>
          {!editing && <button onClick={openNew} className={btnPrimary}>+ New Skill</button>}
        </div>

        {editing ? (
          <div className="card p-4 flex flex-col gap-3">
            {editing.slug ? (
              <div className="text-xs text-ink-dim">Name: <strong className="text-ink">{editing.name}</strong> <span className="text-ink-faint">(fixed once created)</span></div>
            ) : (
              <input className={inputCls} placeholder="Skill name, e.g. Churn Playbook" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            )}
            <input className={inputCls} placeholder="One-line description" value={description} onChange={(e) => setDescription(e.target.value)} />
            <textarea className={inputCls + ' min-h-40 font-mono text-xs resize-y'} placeholder="Markdown playbook: step-by-step instructions this agent should follow..." value={body} onChange={(e) => setBody(e.target.value)} />
            <div className="flex justify-end gap-2">
              <button className={btnSecondary} onClick={cancel}>Cancel</button>
              <button className={btnPrimary} onClick={save}>Save</button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {skills.map((s) => (
              <div key={s.slug} onClick={() => openEdit(s.slug)} className="card card-hover p-3 flex items-center justify-between cursor-pointer">
                <div>
                  <div className="text-sm text-ink font-medium">{s.name}</div>
                  <div className="text-xs text-ink-dim">{s.description}</div>
                </div>
                <button onClick={(e) => remove(s.slug, s.name, e)} className="text-ink-faint hover:text-bad text-lg leading-none px-1">&times;</button>
              </div>
            ))}
            {skills.length === 0 && <div className="text-xs text-ink-faint">No skills yet.</div>}
          </div>
        )}
      </div>
    </div>
  )
}
