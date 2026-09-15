// Pin a chart (from a chat/agent result) into a chosen dashboard, or create
// a new one on the fly - parity port of the old pin-to-dashboard flow.
import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { api } from '../lib/api'
import Modal, { btnPrimary, btnSecondary, inputCls } from './Modal'

export default function PinChartPopover({ chart, onClose }) {
  const [dashboards, setDashboards] = useState([])
  const [selected, setSelected] = useState('')
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [pinned, setPinned] = useState(false)

  useEffect(() => {
    api.listDashboards().then((d) => {
      setDashboards(d.dashboards || [])
      if (d.dashboards?.length) setSelected(d.dashboards[0].id)
      else setCreating(true)
    })
  }, [])

  const pin = async () => {
    try {
      let dashboardId = selected
      if (creating) {
        if (!newName.trim()) return
        const d = await api.createDashboard(newName.trim())
        dashboardId = d.id
      }
      await api.pinChart(dashboardId, {
        title: chart.title || 'Chart', type: chart.type || 'bar',
        labels: chart.labels, data: chart.data, colors: chart.colors,
        points: chart.points, flows: chart.flows,
      })
      setPinned(true)
      setTimeout(onClose, 900)
    } catch (e) { alert(e.message) }
  }

  return (
    <Modal title="Pin chart to dashboard" onClose={onClose}>
      {pinned ? (
        <div className="text-sm text-good py-4 text-center flex items-center justify-center gap-2"><Check size={16} /> Pinned!</div>
      ) : (
        <div className="flex flex-col gap-3">
          {!creating && dashboards.length > 0 && (
            <select className={inputCls} value={selected} onChange={(e) => setSelected(e.target.value)}>
              {dashboards.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          )}
          {!creating && dashboards.length > 0 && (
            <button className="text-xs text-ink-dim hover:text-ink text-left" onClick={() => setCreating(true)}>+ New dashboard instead</button>
          )}
          {creating && (
            <>
              <input className={inputCls} placeholder="New dashboard name" value={newName} onChange={(e) => setNewName(e.target.value)} autoFocus />
              {dashboards.length > 0 && <button className="text-xs text-ink-dim hover:text-ink text-left" onClick={() => setCreating(false)}>Choose existing instead</button>}
            </>
          )}
          <div className="flex justify-end gap-2 mt-2">
            <button className={btnSecondary} onClick={onClose}>Cancel</button>
            <button className={btnPrimary} onClick={pin}>Pin</button>
          </div>
        </div>
      )}
    </Modal>
  )
}
