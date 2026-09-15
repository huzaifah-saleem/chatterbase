// Manual SSE consumer for POST /api/chat/stream (EventSource can't do POST
// bodies). Parses "data: {...}\n\n" frames off the fetch body's reader and
// dispatches progress/result/error events - same protocol the old vanilla
// JS frontend spoke, see app.py's chat_stream().
export async function streamChat(message, history, { onProgress, onResult, onError }) {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
  if (!res.body) throw new Error('Streaming not supported by this browser')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop()
    for (const frame of frames) {
      const line = frame.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      const payload = line.slice(6)
      if (payload === '[DONE]') return
      let msg
      try { msg = JSON.parse(payload) } catch { continue }
      if (msg.type === 'progress') onProgress?.(msg.data.status, msg.data.detail)
      else if (msg.type === 'result') onResult?.(msg.data)
      else if (msg.type === 'error') onError?.(msg.data.error)
    }
  }
}
