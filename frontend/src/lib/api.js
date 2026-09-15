// Thin fetch wrapper over every Chatterbase backend endpoint. One place for
// the request/error shape (every Flask route returns {..} or {error}), so
// views never touch fetch() directly.

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`)
  return data
}

const get = (path) => request(path)
const post = (path, body) => request(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined })
const put = (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body) })
const del = (path) => request(path, { method: 'DELETE' })

export const api = {
  // Status
  mcpHealth: () => get('/api/mcp/health'),
  mcpTools: () => get('/api/mcp/tools'),
  llmHealth: () => get('/api/llm/health'),

  // MCP servers
  listMcpServers: () => get('/api/mcp/servers'),
  addMcpServer: (name, url) => post('/api/mcp/servers', { name, url }),
  updateMcpServer: (id, fields) => put(`/api/mcp/servers/${id}`, fields),
  deleteMcpServer: (id) => del(`/api/mcp/servers/${id}`),
  importMcpServers: (json) => post('/api/mcp/servers/import', { json }),

  // LLM profiles
  listLlmProfiles: () => get('/api/llm/profiles'),
  addLlmProfile: (profile) => post('/api/llm/profiles', profile),
  updateLlmProfile: (id, fields) => put(`/api/llm/profiles/${id}`, fields),
  deleteLlmProfile: (id) => del(`/api/llm/profiles/${id}`),
  activateLlmProfile: (id) => post(`/api/llm/profiles/${id}/activate`),
  llmModels: (url) => get(`/api/llm/models?url=${encodeURIComponent(url)}`),

  // Conversations (Chat)
  listConversations: () => get('/api/conversations'),
  createConversation: (first_message) => post('/api/conversations', { first_message }),
  getConversation: (id) => get(`/api/conversations/${id}`),
  updateConversation: (id, messages) => put(`/api/conversations/${id}`, { messages }),
  renameConversation: (id, title) => put(`/api/conversations/${id}/rename`, { title }),
  deleteConversation: (id) => del(`/api/conversations/${id}`),
  chat: (message, history) => post('/api/chat', { message, history }),

  // Reports
  listReports: () => get('/api/reports'),
  getReport: (id) => get(`/api/reports/${id}`),
  renameReport: (id, title) => put(`/api/reports/${id}/rename`, { title }),
  deleteReport: (id) => del(`/api/reports/${id}`),

  // Dashboards
  listDashboards: () => get('/api/dashboards'),
  createDashboard: (name) => post('/api/dashboards', { name }),
  getDashboard: (id) => get(`/api/dashboards/${id}`),
  renameDashboard: (id, name) => put(`/api/dashboards/${id}/rename`, { name }),
  deleteDashboard: (id) => del(`/api/dashboards/${id}`),
  pinChart: (dashboardId, chart) => post(`/api/dashboards/${dashboardId}/charts`, chart),
  updateChartType: (dashboardId, chartId, type) => put(`/api/dashboards/${dashboardId}/charts/${chartId}`, { type }),
  unpinChart: (dashboardId, chartId) => del(`/api/dashboards/${dashboardId}/charts/${chartId}`),

  // Agent personas
  listPersonas: () => get('/api/agent/personas'),
  createPersona: (persona) => post('/api/agent/personas', persona),
  updatePersona: (id, fields) => put(`/api/agent/personas/${id}`, fields),
  deletePersona: (id) => del(`/api/agent/personas/${id}`),
  importPersona: (payload) => post('/api/agent/personas/import', payload),

  // Agent skills
  listSkills: (personaId) => get(`/api/agent/personas/${personaId}/skills`),
  getSkill: (personaId, slug) => get(`/api/agent/personas/${personaId}/skills/${slug}`),
  createSkill: (personaId, skill) => post(`/api/agent/personas/${personaId}/skills`, skill),
  updateSkill: (personaId, slug, fields) => put(`/api/agent/personas/${personaId}/skills/${slug}`, fields),
  deleteSkill: (personaId, slug) => del(`/api/agent/personas/${personaId}/skills/${slug}`),

  // Agent task runs (gated, one-shot)
  listRuns: (personaId) => get(`/api/agent/runs?persona_id=${encodeURIComponent(personaId ?? '__none__')}`),
  startRun: (request_text, persona_id) => post('/api/agent/run', { request: request_text, persona_id }),
  getRun: (id) => get(`/api/agent/run/${id}`),
  resumeRun: (id, decision) => post(`/api/agent/run/${id}/resume`, { decision }),
  renameRun: (id, title) => put(`/api/agent/run/${id}/rename`, { title }),
  deleteRun: (id) => del(`/api/agent/run/${id}`),

  // Agent chat (multi-turn) - W1
  listAgentChats: (personaId) => get(`/api/agent/personas/${personaId}/chats`),
  createAgentChat: (personaId, first_message) => post(`/api/agent/personas/${personaId}/chats`, { first_message }),
  getAgentChat: (personaId, chatId) => get(`/api/agent/personas/${personaId}/chats/${chatId}`),
  sendAgentChatMessage: (personaId, chatId, message) => post(`/api/agent/personas/${personaId}/chats/${chatId}/message`, { message }),
  resumeAgentChat: (personaId, chatId, decision) => post(`/api/agent/personas/${personaId}/chats/${chatId}/resume`, { decision }),
  renameAgentChat: (personaId, chatId, title) => put(`/api/agent/personas/${personaId}/chats/${chatId}/rename`, { title }),
  deleteAgentChat: (personaId, chatId) => del(`/api/agent/personas/${personaId}/chats/${chatId}`),

  // Knowledge sync - W3
  listDatabases: () => get('/api/databases'),
  getKnowledge: (personaId) => get(`/api/agent/personas/${personaId}/knowledge`),
  syncKnowledge: (personaId, database) => post(`/api/agent/personas/${personaId}/knowledge/sync`, { database }),

  // Activity / observability - W4
  activity: (params = {}) => get(`/api/activity?${new URLSearchParams(params)}`),
  activityStats: () => get('/api/activity/stats'),
  config: () => get('/api/config'),
}
