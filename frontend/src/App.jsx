import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Shell from './components/Shell'
import ChatView from './views/ChatView'
import DashboardsView from './views/DashboardsView'
import AgentsView from './views/AgentsView'
import AgentWorkspace from './views/agent/AgentWorkspace'
import ActivityView from './views/ActivityView'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<ChatView />} />
          <Route path="/dashboards" element={<DashboardsView />} />
          <Route path="/agents" element={<AgentsView />} />
          <Route path="/agents/:id" element={<AgentWorkspace />} />
          <Route path="/activity" element={<ActivityView />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
