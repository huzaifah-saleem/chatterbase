// Multi-turn, mostly-ungated conversation with one agent persona. Unlike
// Tasks (one-shot, every dispatch gated), a chat thread has real memory
// across messages (agent_orchestrator.chat_message/get_chat_history) and
// the task-dispatch gate is off - but run_python is still gated in every
// mode, so a turn can pause mid-conversation for code approval exactly like
// a task dispatch does (see agent_orchestrator.py's W2 notes).
import { useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { streamAgentChat } from '../../lib/useAgentChatStream'
import { Blocks } from '../../components/Blocks'
import { PendingAction } from '../../components/PendingAction'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function ChatTab({ personaId }) {
  const [chats, setChats] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [turns, setTurns] = useState([]) // [{role, content}] or {role:'assistant', blocks}
  const [pending, setPending] = useState(null) // [{tool, args}] when a turn is interrupted
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  // null = not streaming a reply right now; '' or more = tokens received so
  // far for the in-flight reply (the agent's local model "thinks" before
  // answering - it can stay '' for a while, which is exactly when the
  // "Thinking..." indicator below should still show instead of an empty bubble).
  const [streamingText, setStreamingText] = useState(null)
  const scrollRef = useRef(null)

  const loadList = () => api.listAgentChats(personaId).then((d) => setChats(d.chats || []))
  useEffect(() => { loadList(); setActiveId(null); setTurns([]); setPending(null) }, [personaId])
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }) }, [turns, busy, pending, streamingText])

  const openChat = async (id) => {
    setActiveId(id)
    const d = await api.getAgentChat(personaId, id)
    setTurns(d.messages || [])
    setPending(d.status === 'interrupted' ? d.pending_actions : null)
  }
  const newChat = () => { setActiveId(null); setTurns([]); setPending(null) }
  const removeChat = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this chat?')) return
    try {
      await api.deleteAgentChat(personaId, id)
      if (id === activeId) newChat()
      loadList()
    } catch (e) { alert(e.message) }
  }
  const renameChat = async (chat, e) => {
    e.stopPropagation()
    const title = prompt('Rename chat:', chat.title)
    if (!title || title === chat.title) return
    try {
      await api.renameAgentChat(personaId, chat.id, title)
      loadList()
    } catch (e) { alert(e.message) }
  }

  const applyReply = (reply) => {
    if (reply.status === 'interrupted') {
      setPending(reply.pending_actions)
      if (reply.blocks?.length) setTurns((prev) => [...prev, { role: 'assistant', blocks: reply.blocks }])
    } else {
      setPending(null)
      setTurns((prev) => [...prev, { role: 'assistant', blocks: reply.blocks }])
    }
  }

  const send = async () => {
    const text = input.trim()
    if (!text || busy || pending) return
    setInput('')
    setBusy(true)
    setStreamingText('')
    setTurns((prev) => [...prev, { role: 'user', content: text }])

    const isNew = !activeId
    const url = isNew
      ? `/api/agent/personas/${personaId}/chats/stream`
      : `/api/agent/personas/${personaId}/chats/${activeId}/message/stream`
    const body = isNew ? { first_message: text } : { message: text }

    try {
      await streamAgentChat(url, body, {
        onChat: (chat) => setActiveId(chat.id),
        onToken: (t) => setStreamingText((prev) => (prev ?? '') + t),
        onResult: (data) => { setStreamingText(null); applyReply(data); loadList() },
        onError: (err) => { setStreamingText(null); setTurns((prev) => [...prev, { role: 'assistant', content: `Error: ${err}` }]) },
      })
    } catch (e) {
      setStreamingText(null)
      setTurns((prev) => [...prev, { role: 'assistant', content: `Error: ${e.message}` }])
    } finally {
      setBusy(false)
      setStreamingText(null)
    }
  }

  const resume = async (decision) => {
    setBusy(true)
    setStreamingText('')
    try {
      await streamAgentChat(`/api/agent/personas/${personaId}/chats/${activeId}/resume/stream`, { decision }, {
        onToken: (t) => setStreamingText((prev) => (prev ?? '') + t),
        onResult: (data) => { setStreamingText(null); applyReply(data); loadList() },
        onError: (err) => { setStreamingText(null); alert(err) },
      })
    } catch (e) {
      setStreamingText(null)
      alert(e.message)
    } finally {
      setBusy(false)
      setStreamingText(null)
    }
  }

  return (
    <div className="flex-1 flex min-h-0">
      <aside className="w-64 shrink-0 border-r border-edge flex flex-col">
        <div className="p-3">
          <button onClick={newChat} className="w-full py-2.5 rounded-lg grad text-white text-sm font-semibold hover:opacity-90 transition">+ New Chat</button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2 flex flex-col gap-1">
          {chats.map((c) => (
            <div
              key={c.id}
              onClick={() => openChat(c.id)}
              className={`group flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer transition
                ${c.id === activeId ? 'bg-accent/15 text-accent-hot' : 'text-ink-dim hover:bg-panel hover:text-ink'}`}
            >
              <span className="truncate">{c.title}</span>
              <span className="flex items-center gap-1 opacity-60 group-hover:opacity-100 shrink-0">
                <button onClick={(e) => renameChat(c, e)} className="text-ink-faint hover:text-ink transition">✏️</button>
                <button onClick={(e) => removeChat(c.id, e)} className="text-ink-faint hover:text-bad transition">&times;</button>
              </span>
            </div>
          ))}
          {chats.length === 0 && <div className="px-3 py-2 text-xs text-ink-faint">No chats yet</div>}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {turns.length === 0 ? (
            <div className="h-full flex items-center justify-center text-ink-faint text-sm">Start a conversation - this agent remembers the whole thread.</div>
          ) : (
            <div className="max-w-3xl mx-auto p-6 flex flex-col gap-4">
              {turns.map((t, i) => (
                <div key={i} className={`flex ${t.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`rounded-2xl px-4 py-3 max-w-[85%] ${t.role === 'user' ? 'bg-accent text-white text-sm' : 'card w-full'}`}>
                    {t.role === 'user'
                      ? t.content
                      : t.blocks ? <Blocks blocks={t.blocks} /> : <div className="md text-sm text-ink"><ReactMarkdown remarkPlugins={[remarkGfm]}>{t.content || ''}</ReactMarkdown></div>}
                  </div>
                </div>
              ))}
              {pending && (
                <div className="card p-4 flex flex-col gap-3">
                  <div className="flex flex-col gap-2">
                    {pending.map((a, i) => <PendingAction key={i} tool={a.tool} args={a.args} />)}
                  </div>
                  {busy ? (
                    <div className="text-xs text-ink-faint flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-accent pulse" /> Running...</div>
                  ) : (
                    <div className="flex gap-2 justify-end">
                      <button onClick={() => resume('reject')} className="text-xs px-3 py-1.5 rounded-lg bg-panel border border-edge text-ink-dim hover:text-bad hover:border-bad/50 transition">Reject</button>
                      <button onClick={() => resume('approve')} className="text-xs px-3 py-1.5 rounded-lg grad text-white font-medium hover:opacity-90 transition">Approve &amp; Run</button>
                    </div>
                  )}
                </div>
              )}
              {streamingText !== null && !pending && (
                <div className="flex justify-start">
                  <div className="card px-4 py-3 max-w-[85%] w-full text-sm text-ink-dim">
                    {streamingText ? (
                      <div className="md text-sm text-ink"><ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingText}</ReactMarkdown></div>
                    ) : (
                      <div className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-accent pulse" /> Thinking...</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="border-t border-edge p-4">
          <div className="max-w-3xl mx-auto flex gap-2">
            <textarea
              className="flex-1 resize-none rounded-xl bg-panel border border-edge px-4 py-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition disabled:opacity-50"
              rows={1}
              placeholder={pending ? 'Respond to the pending approval above first...' : 'Message this agent...'}
              value={input}
              disabled={!!pending}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            />
            <button onClick={send} disabled={busy || !!pending} className="px-5 rounded-xl grad text-white text-sm font-semibold hover:opacity-90 transition disabled:opacity-40">Send</button>
          </div>
        </div>
      </div>
    </div>
  )
}
