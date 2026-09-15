// Manual SSE consumer for the agent-chat streaming routes (POST, so
// EventSource can't be used) - mirrors useChatStream.js's frame parsing,
// generalized for the agent-chat event shapes: "chat" (new chat record,
// stream-create only), "token" (one content delta), "result" (final
// status/pending_actions/blocks), "error".
export async function streamAgentChat(url, body, { onChat, onToken, onResult, onError }) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
      if (msg.type === 'chat') onChat?.(msg.data)
      else if (msg.type === 'token') onToken?.(msg.text)
      else if (msg.type === 'result') onResult?.(msg.data)
      else if (msg.type === 'error') onError?.(msg.data.error)
    }
  }
}
