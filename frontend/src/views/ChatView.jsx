// Plain chat: conversation list + streaming Q&A against the connected
// database via chat_handler.py's tool-calling loop. Parity port of the
// original chat tab, restyled.
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { streamChat } from '../lib/useChatStream'
import { parseChatResponse } from '../lib/parseChatResponse'
import { Blocks } from '../components/Blocks'
import PinChartPopover from '../components/PinChartPopover'

const SUGGESTIONS = [
  { icon: '🗄️', text: 'What databases do I have access to?' },
  { icon: '📋', text: 'Show me the tables in a database, with row counts' },
  { icon: '🔍', text: 'Check for data quality issues like missing values' },
  { icon: '📊', text: 'Analyze and chart the size of my databases' },
]

export default function ChatView() {
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(null)
  const [pinChart, setPinChart] = useState(null)
  const scrollRef = useRef(null)

  const loadList = () => api.listConversations().then((d) => setConversations(d.conversations || []))
  useEffect(() => { loadList() }, [])
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }) }, [messages, progress])

  const openConversation = async (id) => {
    const c = await api.getConversation(id)
    setActiveId(id)
    setMessages(c.messages || [])
  }
  const newChat = () => { setActiveId(null); setMessages([]) }
  const deleteConversation = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this conversation?')) return
    await api.deleteConversation(id)
    if (id === activeId) newChat()
    loadList()
  }

  const send = async (text) => {
    const messageText = (text ?? input).trim()
    if (!messageText || busy) return
    setInput('')
    setBusy(true)
    setProgress('Thinking...')

    let convId = activeId
    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    const nextMessages = [...messages, { role: 'user', content: messageText }]
    setMessages(nextMessages)

    if (!convId) {
      const c = await api.createConversation(messageText)
      convId = c.id
      setActiveId(convId)
      loadList()
    }

    try {
      await streamChat(messageText, history, {
        onProgress: (status, detail) => setProgress(detail || status),
        onResult: async (result) => {
          const finalMessages = [...nextMessages, { role: 'assistant', content: result.error ? `Error: ${result.error}` : result.response }]
          setMessages(finalMessages)
          await api.updateConversation(convId, finalMessages)
          loadList()
        },
        onError: (err) => {
          setMessages([...nextMessages, { role: 'assistant', content: `Error: ${err}` }])
        },
      })
    } catch (e) {
      setMessages([...nextMessages, { role: 'assistant', content: `Error: ${e.message}` }])
    } finally {
      setBusy(false)
      setProgress(null)
    }
  }

  return (
    <div className="flex-1 flex min-h-0">
      <aside className="w-64 shrink-0 border-r border-edge flex flex-col">
        <div className="p-3">
          <button onClick={newChat} className="w-full py-2.5 rounded-lg grad text-white text-sm font-semibold hover:opacity-90 transition">+ New Chat</button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2 flex flex-col gap-1">
          {conversations.map((c) => (
            <div
              key={c.id}
              onClick={() => openConversation(c.id)}
              className={`group flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer transition
                ${c.id === activeId ? 'bg-accent/15 text-accent-hot' : 'text-ink-dim hover:bg-panel hover:text-ink'}`}
            >
              <span className="truncate">{c.title}</span>
              <button onClick={(e) => deleteConversation(c.id, e)} className="opacity-0 group-hover:opacity-100 text-ink-faint hover:text-bad transition shrink-0">&times;</button>
            </div>
          ))}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center px-8 text-center max-w-xl mx-auto">
              <div className="w-16 h-16 rounded-2xl grad flex items-center justify-center text-2xl mb-4">💬</div>
              <h2 className="text-xl font-semibold text-ink mb-1">Chatterbase</h2>
              <p className="text-sm text-ink-dim mb-6">Ask about your Teradata database in plain English — I'll query, analyze, and visualize the results.</p>
              <div className="grid grid-cols-2 gap-2 w-full">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} onClick={() => send(s.text)} className="card card-hover text-left p-3 text-sm text-ink-dim flex items-start gap-2">
                    <span>{s.icon}</span><span>{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto p-6 flex flex-col gap-4">
              {messages.map((m, i) => (
                <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`rounded-2xl px-4 py-3 max-w-[85%] ${m.role === 'user' ? 'bg-accent text-white text-sm' : 'card w-full'}`}>
                    {m.role === 'user'
                      ? m.content
                      : <Blocks blocks={parseChatResponse(m.content)} onPinChart={(chart) => setPinChart(chart)} />}
                  </div>
                </div>
              ))}
              {busy && (
                <div className="flex justify-start">
                  <div className="card px-4 py-3 text-sm text-ink-dim flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent pulse" /> {progress || 'Working...'}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="border-t border-edge p-4">
          <div className="max-w-3xl mx-auto flex gap-2">
            <textarea
              className="flex-1 resize-none rounded-xl bg-panel border border-edge px-4 py-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition"
              rows={1}
              placeholder="Ask about your Teradata database..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            />
            <button onClick={() => send()} disabled={busy} className="px-5 rounded-xl grad text-white text-sm font-semibold hover:opacity-90 transition disabled:opacity-40">Send</button>
          </div>
        </div>
      </div>

      {pinChart && <PinChartPopover chart={pinChart} onClose={() => setPinChart(null)} />}
    </div>
  )
}
