// The plain /api/chat path (chat_handler.py + get_summary_prompt) embeds
// chart specs as ```chart fenced JSON blocks inside the prose response,
// rather than returning structured blocks like the agent endpoints do.
// This splits response text into the same {type:"text"|"chart"} block
// vocabulary Blocks.jsx already renders, so both paths share one renderer.
export function parseChatResponse(text) {
  if (!text) return []
  const re = /```chart\s*([\s\S]*?)```/g
  const blocks = []
  let last = 0
  let match
  while ((match = re.exec(text))) {
    const before = text.slice(last, match.index).trim()
    if (before) blocks.push({ type: 'text', content: before })
    try {
      const spec = JSON.parse(match[1].trim())
      blocks.push({ type: 'chart', chart: spec })
    } catch { /* malformed chart JSON - skip it, keep surrounding text */ }
    last = re.lastIndex
  }
  const rest = text.slice(last).trim()
  if (rest) blocks.push({ type: 'text', content: rest })
  return blocks.length ? blocks : [{ type: 'text', content: text }]
}
